from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import aiohttp

from ..api.client import DouyinAPIClient
from .exceptions import DownloadCancelled
from .queue_manager import QueueManager


class Downloader:
    RETRYABLE_STATUS_CODES = {403, 408, 409, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        api_client: DouyinAPIClient,
        save_dir: Path,
        max_workers: int = 2,
        cancel_event: threading.Event | None = None,
    ):
        self.api_client = api_client
        self.save_dir = save_dir
        self.cancel_event = cancel_event
        self.queue_manager = QueueManager(max_workers, cancel_event=cancel_event)
        self.current_sec_user_id = None
        self.failed_entries: list[dict] = []

    async def _download_item(self, item: dict):
        self._ensure_not_cancelled()
        media_entries = self.build_media_entries(item)
        if not media_entries:
            print(f"作品 {item.get('aweme_id')} 没有可下载的媒体数据，跳过下载。")
            return

        headers = self.api_client._get_headers()
        if self.current_sec_user_id:
            headers["referer"] = f"https://www.douyin.com/user/{self.current_sec_user_id}"

        async with aiohttp.ClientSession(headers=headers) as session:
            for entry in media_entries:
                self._ensure_not_cancelled()
                await self._download_entry(session, entry)

    def _get_highest_quality_url(self, video: dict) -> str | None:
        candidate_urls = self._collect_video_candidate_urls(video)
        if candidate_urls:
            return candidate_urls[0]
        return None

    def build_filename(self, item: dict) -> str:
        video_id = item["aweme_id"]
        desc = item.get("desc", "no_desc")
        valid_desc = "".join(c for c in desc if c.isalnum() or c in (" ", "_")).strip() or "no_desc"
        return f"{valid_desc}_{video_id}.mp4"

    def build_media_entries(self, item: dict) -> list[dict]:
        image_entries = self._build_image_entries(item)
        if image_entries and self._looks_like_image_post(item):
            return image_entries

        video = item.get("video")
        if video:
            candidate_urls = self._collect_video_candidate_urls(video)
            if candidate_urls:
                return [
                    {
                        "filename": self.build_filename(item),
                        "url": candidate_urls[0],
                        "candidate_urls": candidate_urls,
                        "media_id": item.get("aweme_id"),
                        "description": item.get("desc", ""),
                        "type": "video",
                    }
                ]

        if image_entries:
            return image_entries
        return []

    def fetch_user_posts(self, sec_user_id: str) -> list[dict]:
        aweme_list = []
        max_cursor = 0
        has_more = True

        print("正在获取所有作品列表...")
        while has_more:
            self._ensure_not_cancelled()
            data = self.api_client.get_user_posts(sec_user_id, max_cursor)
            if not data:
                break

            aweme_items = data.get("aweme_list", [])
            if not aweme_items:
                break

            aweme_list.extend(aweme_items)
            has_more = data.get("has_more", False)
            max_cursor = data.get("max_cursor", 0)
            print(f"已获取 {len(aweme_list)} 个作品...", end="\r")

        print(f"\n共获取到 {len(aweme_list)} 个作品，开始并行下载...")
        if not aweme_list and getattr(self.api_client, "last_error", None):
            raise RuntimeError(self.api_client.last_error)
        return aweme_list

    async def download_aweme(self, aweme_detail: dict):
        self.failed_entries = []
        self._ensure_not_cancelled()
        self.current_sec_user_id = (
            aweme_detail.get("author", {}).get("sec_uid")
            if isinstance(aweme_detail.get("author"), dict)
            else None
        )
        await self._download_item(aweme_detail)

    async def _download_entry(self, session: aiohttp.ClientSession, entry: dict):
        self._ensure_not_cancelled()
        filename = entry["filename"]
        filepath = self.save_dir / filename

        if filepath.exists():
            print(f"文件已存在: {filename}")
            return

        print(f"准备下载: {filename}")
        try:
            await self._download_with_retry(session, entry, filepath)
            print(f"下载成功: {filename}")
        except Exception as exc:
            self._record_failed_entry(entry, exc)
            print(f"下载失败: {filename}, 错误: {exc}")
            raise

    async def _download_with_retry(self, session: aiohttp.ClientSession, entry: dict, filepath: Path, progress_callback=None):
        candidate_urls = self._normalize_candidate_urls(entry)
        if not candidate_urls:
            raise ValueError(f"文件 {entry.get('filename', 'unknown')} 没有可用下载链接")

        max_attempts = self._max_attempts_for_entry(entry)
        last_exc = None
        for attempt in range(max_attempts):
            self._ensure_not_cancelled()
            for media_url in candidate_urls:
                self._ensure_not_cancelled()
                try:
                    await self._stream_to_file(session, media_url, filepath, progress_callback=progress_callback)
                    return
                except DownloadCancelled:
                    self._cleanup_partial_file(filepath)
                    raise
                except aiohttp.ClientResponseError as exc:
                    last_exc = exc
                    self._cleanup_partial_file(filepath)
                    if exc.status not in self.RETRYABLE_STATUS_CODES:
                        raise
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError, KeyError, IndexError) as exc:
                    last_exc = exc
                    self._cleanup_partial_file(filepath)

            if attempt < max_attempts - 1:
                await asyncio.sleep(self._retry_delay_seconds(attempt, entry))

        if last_exc:
            raise last_exc
        raise RuntimeError(f"文件 {entry.get('filename', 'unknown')} 下载失败")

    async def _stream_to_file(self, session: aiohttp.ClientSession, media_url: str, filepath: Path, progress_callback=None):
        async with session.get(media_url) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            downloaded_size = 0
            started_at = asyncio.get_running_loop().time()

            with open(filepath, "wb") as file:
                while True:
                    self._ensure_not_cancelled()
                    chunk = await response.content.read(8192)
                    if not chunk:
                        break
                    file.write(chunk)
                    downloaded_size += len(chunk)
                    if progress_callback:
                        elapsed = max(asyncio.get_running_loop().time() - started_at, 0.001)
                        progress_callback(downloaded_size, total_size, downloaded_size / elapsed)

    def _normalize_candidate_urls(self, entry: dict) -> list[str]:
        seen = set()
        urls = []
        for value in entry.get("candidate_urls") or [entry.get("url")]:
            if not isinstance(value, str) or not value.startswith("http"):
                continue
            if value in seen:
                continue
            seen.add(value)
            urls.append(value)
        return urls

    def _max_attempts_for_entry(self, entry: dict) -> int:
        if entry.get("type") in {"image", "motion"}:
            return 4
        return 3

    def _retry_delay_seconds(self, attempt: int, entry: dict) -> float:
        base = 1.2 if entry.get("type") in {"image", "motion"} else 0.8
        return min(base * (2 ** attempt), 8.0)

    def _cleanup_partial_file(self, filepath: Path) -> None:
        if filepath.exists():
            filepath.unlink()

    def _record_failed_entry(self, entry: dict, exc: Exception) -> None:
        self.failed_entries.append(
            {
                "filename": entry.get("filename", ""),
                "type": entry.get("type", ""),
                "media_id": entry.get("media_id", ""),
                "description": entry.get("description", ""),
                "url": entry.get("url", ""),
                "candidate_urls": list(entry.get("candidate_urls") or []),
                "error": str(exc),
            }
        )

    def export_failed_entries(self) -> tuple[Path, Path] | None:
        if not self.failed_entries:
            return None

        json_path = self.save_dir / "failed_downloads.json"
        text_path = self.save_dir / "failed_downloads.txt"

        json_path.write_text(
            json.dumps(
                {
                    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "failed_count": len(self.failed_entries),
                    "items": self.failed_entries,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        lines = []
        for item in self.failed_entries:
            lines.append(f"文件: {item['filename']}")
            lines.append(f"类型: {item['type']}")
            lines.append(f"作品ID: {item['media_id']}")
            lines.append(f"错误: {item['error']}")
            for index, url in enumerate(item.get("candidate_urls", []), start=1):
                lines.append(f"候选链接{index}: {url}")
            lines.append("")
        text_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        return json_path, text_path

    def _build_image_entries(self, item: dict) -> list[dict]:
        base_name = self.build_base_name(item)
        image_nodes = self._collect_image_nodes(item)
        entries: list[dict] = []
        seen_assets: set[tuple[str | None, str | None]] = set()
        image_index = 0

        for image_node in image_nodes:
            image_url = self._extract_image_url(image_node)
            motion_url = self._extract_motion_url(image_node)
            asset_key = (image_url, motion_url)
            if asset_key in seen_assets:
                continue
            seen_assets.add(asset_key)

            image_index += 1
            index = image_index
            if image_url:
                candidate_urls = self._collect_image_candidate_urls(image_node)
                extension = self._guess_extension(image_url, default=".jpg")
                entries.append(
                    {
                        "filename": f"{base_name}_{index:02d}{extension}",
                        "url": image_url,
                        "candidate_urls": candidate_urls or [image_url],
                        "media_id": item.get("aweme_id"),
                        "description": item.get("desc", ""),
                        "type": "image",
                    }
                )

            if motion_url:
                motion_candidates = self._collect_motion_candidate_urls(image_node)
                extension = self._guess_extension(motion_url, default=".mp4")
                entries.append(
                    {
                        "filename": f"{base_name}_{index:02d}_motion{extension}",
                        "url": motion_url,
                        "candidate_urls": motion_candidates or [motion_url],
                        "media_id": item.get("aweme_id"),
                        "description": item.get("desc", ""),
                        "type": "motion",
                    }
                )

        return entries

    def build_base_name(self, item: dict) -> str:
        media_id = item["aweme_id"]
        desc = item.get("desc", "no_desc")
        valid_desc = "".join(c for c in desc if c.isalnum() or c in (" ", "_")).strip() or "no_desc"
        return f"{valid_desc}_{media_id}"

    def _collect_image_nodes(self, item: dict) -> list[dict]:
        nodes = []
        for key in ("images", "image_list", "image_infos", "origin_images"):
            if isinstance(item.get(key), list):
                nodes.extend(node for node in item[key] if isinstance(node, dict))

        image_post_info = item.get("image_post_info")
        if isinstance(image_post_info, dict):
            for key in ("images", "image_list"):
                image_list = image_post_info.get(key)
                if isinstance(image_list, list):
                    nodes.extend(node for node in image_list if isinstance(node, dict))

        return nodes

    def _extract_image_url(self, image_node: dict) -> str | None:
        for key in (
            "display_image",
            "origin_image",
            "image_url",
            "large_image",
            "download_image",
            "owner_watermark_image",
            "thumbnail",
        ):
            nested = image_node.get(key)
            url = self._extract_url_from_node(
                nested,
                preferred_keys=(
                    "watermark_free_download_url_list",
                    "origin_url_list",
                    "url_list",
                    "download_url_list",
                    "download_url",
                    "url",
                ),
            )
            if url:
                return url
        return self._extract_url_from_node(
            image_node,
            preferred_keys=(
                "watermark_free_download_url_list",
                "origin_url_list",
                "url_list",
                "download_url_list",
                "download_url",
                "url",
            ),
        )

    def _extract_motion_url(self, image_node: dict) -> str | None:
        for key in ("live_photo_video", "video", "motion_photo", "motion_video"):
            nested = image_node.get(key)
            url = self._extract_url_from_node(
                nested,
                preferred_keys=("play_addr_h264", "play_addr", "url_list", "download_url_list", "url"),
            )
            if url:
                return url
        return None

    def _collect_video_candidate_urls(self, video: dict) -> list[str]:
        urls: list[str] = []
        bitrates = video.get("bit_rate")
        if isinstance(bitrates, list):
            ranked_bitrates = sorted(
                (item for item in bitrates if isinstance(item, dict)),
                key=self._score_video_variant,
                reverse=True,
            )
            for bitrate in ranked_bitrates:
                urls.extend(
                    self._extract_all_urls_from_node(
                        bitrate,
                        preferred_keys=("play_addr_h264", "play_addr", "url_list", "download_url_list", "url"),
                    )
                )

        for key in ("play_addr_h264", "play_addr", "download_addr"):
            urls.extend(self._extract_all_urls_from_node(video.get(key)))
        return self._deduplicate_urls(urls)

    def _score_video_variant(self, variant: dict) -> tuple[int, int, int, int]:
        bit_rate = int(variant.get("bit_rate") or 0)
        play_addr = variant.get("play_addr") if isinstance(variant.get("play_addr"), dict) else {}
        width = int(play_addr.get("width") or variant.get("width") or 0)
        height = int(play_addr.get("height") or variant.get("height") or 0)
        gear_name = str(variant.get("gear_name") or "")
        quality_bonus = 0
        if "1080" in gear_name:
            quality_bonus = 3
        elif "720" in gear_name:
            quality_bonus = 2
        elif "540" in gear_name:
            quality_bonus = 1
        return (bit_rate, height, width, quality_bonus)

    def _collect_image_candidate_urls(self, image_node: dict) -> list[str]:
        urls: list[str] = []
        for key in (
            "display_image",
            "origin_image",
            "image_url",
            "large_image",
            "download_image",
            "owner_watermark_image",
            "thumbnail",
        ):
            urls.extend(
                self._extract_all_urls_from_node(
                    image_node.get(key),
                    preferred_keys=(
                        "watermark_free_download_url_list",
                        "origin_url_list",
                        "url_list",
                        "download_url_list",
                        "download_url",
                        "url",
                    ),
                )
            )

        urls.extend(
            self._extract_all_urls_from_node(
                image_node,
                preferred_keys=(
                    "watermark_free_download_url_list",
                    "origin_url_list",
                    "url_list",
                    "download_url_list",
                    "download_url",
                    "url",
                ),
            )
        )
        return self._deduplicate_urls(urls)

    def _collect_motion_candidate_urls(self, image_node: dict) -> list[str]:
        urls: list[str] = []
        for key in ("live_photo_video", "video", "motion_photo", "motion_video"):
            urls.extend(
                self._extract_all_urls_from_node(
                    image_node.get(key),
                    preferred_keys=("play_addr_h264", "play_addr", "url_list", "download_url_list", "url"),
                )
            )
        return self._deduplicate_urls(urls)

    def _extract_url_from_node(self, node, preferred_keys: tuple[str, ...] | None = None) -> str | None:
        if isinstance(node, str) and node.startswith("http"):
            return node
        if isinstance(node, list):
            for value in node:
                url = self._extract_url_from_node(value, preferred_keys=preferred_keys)
                if url:
                    return url
        if isinstance(node, dict):
            keys = preferred_keys or (
                "watermark_free_download_url_list",
                "origin_url_list",
                "url_list",
                "download_url_list",
                "play_addr_h264",
                "play_addr",
            )
            for key in keys:
                if key in node:
                    url = self._extract_url_from_node(node.get(key), preferred_keys=preferred_keys)
                    if url:
                        return url
            for key in ("url", "download_url", "uri"):
                value = node.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    return value
        return None

    def _extract_all_urls_from_node(self, node, preferred_keys: tuple[str, ...] | None = None) -> list[str]:
        urls: list[str] = []
        if isinstance(node, str) and node.startswith("http"):
            return [node]
        if isinstance(node, list):
            for value in node:
                urls.extend(self._extract_all_urls_from_node(value, preferred_keys=preferred_keys))
            return urls
        if isinstance(node, dict):
            keys = preferred_keys or (
                "watermark_free_download_url_list",
                "origin_url_list",
                "url_list",
                "download_url_list",
                "play_addr_h264",
                "play_addr",
            )
            for key in keys:
                if key in node:
                    urls.extend(self._extract_all_urls_from_node(node.get(key), preferred_keys=preferred_keys))
            for key in ("url", "download_url", "uri"):
                value = node.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    urls.append(value)
        return urls

    def _deduplicate_urls(self, urls: list[str]) -> list[str]:
        seen = set()
        result = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            result.append(url)
        return result

    def _looks_like_image_post(self, item: dict) -> bool:
        if item.get("aweme_type") in {68, 150}:
            return True
        return bool(self._collect_image_nodes(item))

    def _guess_extension(self, media_url: str, default: str) -> str:
        parsed = urlparse(media_url)
        suffix = Path(parsed.path).suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4"}:
            return suffix
        if "mime_type=image_webp" in media_url:
            return ".webp"
        if "mime_type=image_png" in media_url:
            return ".png"
        if "mime_type=video_mp4" in media_url:
            return ".mp4"
        return default

    async def download_user_posts(self, sec_user_id: str):
        self.current_sec_user_id = sec_user_id
        self.failed_entries = []
        self._ensure_not_cancelled()
        aweme_list = self.fetch_user_posts(sec_user_id)
        await self.queue_manager.download_batch(self._download_item, aweme_list)

    def _ensure_not_cancelled(self) -> None:
        if self.cancel_event and self.cancel_event.is_set():
            raise DownloadCancelled("下载已取消")
