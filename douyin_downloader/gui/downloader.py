from __future__ import annotations

import asyncio
import time
from typing import Callable

import aiohttp

from douyin_downloader.downloader.downloader import Downloader
from douyin_downloader.downloader.exceptions import DownloadCancelled


class GUIDownloader(Downloader):
    def __init__(
        self,
        api_client,
        save_dir,
        max_workers: int = 2,
        cancel_event=None,
        progress_callback: Callable[[dict], None] | None = None,
        error_callback: Callable[[dict], None] | None = None,
        queue_init_callback: Callable[[list[str]], None] | None = None,
        queue_update_callback: Callable[[str, str, str, str, str, str], None] | None = None,
    ):
        super().__init__(api_client, save_dir, max_workers=max_workers, cancel_event=cancel_event)
        self.progress_callback = progress_callback
        self.error_callback = error_callback
        self.queue_init_callback = queue_init_callback
        self.queue_update_callback = queue_update_callback
        self.download_stats = self._fresh_stats()
        self._last_progress_emit = 0.0
        self._last_queue_emit_at: dict[str, float] = {}
        self._progress_emit_interval = 0.15
        self._queue_emit_interval = 0.15

    @staticmethod
    def _fresh_stats() -> dict:
        return {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "current_file": "",
            "current_progress": 0,
            "download_speed": 0,
            "start_time": time.time(),
        }

    async def download_user_posts(self, sec_user_id: str):
        self.current_sec_user_id = sec_user_id
        self.download_stats = self._fresh_stats()
        self.failed_entries = []
        self._last_progress_emit = 0.0
        self._last_queue_emit_at.clear()
        aweme_list = self.fetch_user_posts(sec_user_id)
        queue_files = [entry["filename"] for item in aweme_list for entry in self.build_media_entries(item)]
        self.download_stats["total"] = len(queue_files)
        self._emit_progress(force=True)

        if self.queue_init_callback:
            self.queue_init_callback(queue_files)

        await self.queue_manager.download_batch(self._download_item, aweme_list)

    async def download_aweme(self, aweme_detail: dict):
        self.current_sec_user_id = (
            aweme_detail.get("author", {}).get("sec_uid")
            if isinstance(aweme_detail.get("author"), dict)
            else None
        )
        self.download_stats = self._fresh_stats()
        self.failed_entries = []
        self._last_progress_emit = 0.0
        self._last_queue_emit_at.clear()

        media_entries = self.build_media_entries(aweme_detail)
        queue_files = [entry["filename"] for entry in media_entries]
        self.download_stats["total"] = len(queue_files)
        self._emit_progress(force=True)

        if self.queue_init_callback:
            self.queue_init_callback(queue_files)

        await self._download_item(aweme_detail)

    async def _download_item(self, item: dict):
        self._ensure_not_cancelled()
        media_entries = self.build_media_entries(item)
        if not media_entries:
            self._mark_skipped(self.build_base_name(item))
            return

        headers = self.api_client._get_headers()
        if self.current_sec_user_id:
            headers["referer"] = f"https://www.douyin.com/user/{self.current_sec_user_id}"

        async with aiohttp.ClientSession(headers=headers) as session:
            for entry in media_entries:
                self._ensure_not_cancelled()
                await self._download_media_entry(session, entry)

    async def _download_media_entry(self, session: aiohttp.ClientSession, entry: dict):
        self._ensure_not_cancelled()
        filename = entry["filename"]
        filepath = self.save_dir / filename

        if filepath.exists():
            self._mark_skipped(filename)
            return

        self.download_stats["current_file"] = filename
        self.download_stats["current_progress"] = 0
        self.download_stats["download_speed"] = 0
        self._emit_queue_update(filename, "下载中", "0%", "-", "-", "-", force=True)
        self._emit_progress(force=True)

        try:
            await self._download_with_retry(
                session,
                entry,
                filepath,
                progress_callback=lambda downloaded_size, total_size, speed: self._update_current_progress(
                    filename, downloaded_size, total_size, speed
                ),
            )

            self.download_stats["completed"] += 1
            self.download_stats["current_file"] = ""
            self.download_stats["current_progress"] = 0
            self._emit_queue_update(filename, "已完成", "100%", "-", "-", "-", force=True)
            self._emit_progress(force=True)

        except DownloadCancelled:
            self._cleanup_partial_file(filepath)
            self.download_stats["current_file"] = ""
            self.download_stats["current_progress"] = 0
            self._emit_queue_update(filename, "已取消", "-", "-", "-", "-", force=True)
            self._emit_progress(force=True)
            raise

        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, KeyError, IndexError) as exc:
            self._cleanup_partial_file(filepath)
            self._record_failed_entry(entry, exc)
            self.download_stats["failed"] += 1
            self.download_stats["current_file"] = ""
            self.download_stats["current_progress"] = 0
            error_text = self._format_download_error(exc)
            self._emit_queue_update(filename, "错误", "0%", "-", "-", error_text, force=True)
            if self.error_callback:
                self.error_callback(
                    {
                        "filename": filename,
                        "error": error_text,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            self._emit_progress(force=True)

    def _update_current_progress(self, filename: str, downloaded_size: int, total_size: int, speed: float) -> None:
        progress = downloaded_size / total_size * 100 if total_size > 0 else 0
        self.download_stats["current_file"] = filename
        self.download_stats["current_progress"] = progress
        self.download_stats["download_speed"] = speed
        self._emit_queue_update(
            filename,
            "下载中",
            f"{progress:.1f}%",
            f"{speed / 1024:.1f} KB/s",
            f"{downloaded_size / 1024 / 1024:.1f} MB",
            "-",
        )
        self._emit_progress()

    def _format_download_error(self, exc: Exception) -> str:
        if isinstance(exc, aiohttp.ClientResponseError) and exc.status in self.RETRYABLE_STATUS_CODES:
            return f"{exc.status} Forbidden/RateLimit，疑似触发风控，自动重试后仍失败"
        return str(exc)

    def _mark_skipped(self, filename: str) -> None:
        self.download_stats["skipped"] += 1
        if filename:
            self._emit_queue_update(filename, "已跳过", "-", "-", "-", "-", force=True)
        self._emit_progress(force=True)

    def _emit_progress(self, *, force: bool = False) -> None:
        if self.progress_callback:
            now = time.time()
            if not force and now - self._last_progress_emit < self._progress_emit_interval:
                return
            self._last_progress_emit = now
            self.progress_callback(self.download_stats.copy())

    def _emit_queue_update(
        self,
        filename: str,
        status: str,
        progress: str,
        speed: str,
        size: str,
        error: str,
        *,
        force: bool = False,
    ) -> None:
        if not self.queue_update_callback:
            return
        now = time.time()
        last_emit = self._last_queue_emit_at.get(filename, 0.0)
        if not force and now - last_emit < self._queue_emit_interval:
            return
        self._last_queue_emit_at[filename] = now
        self.queue_update_callback(filename, status, progress, speed, size, error)
