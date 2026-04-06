from __future__ import annotations

import asyncio
from pathlib import Path

from douyin_downloader.api.client import DouyinAPIClient
from douyin_downloader.cookies.manager import CookieManager
from douyin_downloader.cookies.parser import (
    extract_author_url_from_curl,
    extract_sec_user_id_from_curl,
    read_curl_text,
)
from douyin_downloader.downloader.downloader import Downloader
from douyin_downloader.models import DownloadCallbacks, DownloadRequest, DownloadTarget
from douyin_downloader.utils.aweme_extractor import extract_aweme_id, extract_share_url
from douyin_downloader.utils.sec_user_id_extractor import extract_sec_user_id


class DownloadService:
    def __init__(self, gui_downloader_factory=None):
        self.gui_downloader_factory = gui_downloader_factory

    def resolve_target(self, request: DownloadRequest, api_client: DouyinAPIClient | None = None) -> DownloadTarget:
        url = extract_share_url(request.url.strip())
        if url:
            direct_aweme_id = extract_aweme_id(url)
            if direct_aweme_id:
                return DownloadTarget(kind="aweme", identifier=direct_aweme_id, source_url=url, resolved_url=url)

            sec_user_id = extract_sec_user_id(url)
            if sec_user_id:
                return DownloadTarget(kind="user", identifier=sec_user_id, source_url=url, resolved_url=url)

            resolved_url = api_client.resolve_url(url) if api_client else url
            resolved_aweme_id = extract_aweme_id(resolved_url)
            if resolved_aweme_id:
                return DownloadTarget(
                    kind="aweme",
                    identifier=resolved_aweme_id,
                    source_url=url,
                    resolved_url=resolved_url,
                )

            resolved_sec_user_id = extract_sec_user_id(resolved_url)
            if resolved_sec_user_id:
                return DownloadTarget(
                    kind="user",
                    identifier=resolved_sec_user_id,
                    source_url=url,
                    resolved_url=resolved_url,
                )

            if api_client and getattr(api_client, "last_error_kind", None) == "network" and api_client.last_error:
                raise RuntimeError(api_client.last_error)

        curl_text = self._resolve_curl_text(request)
        if not curl_text:
            raise ValueError("无法从当前输入中识别作者主页或作品链接，请检查 URL / cURL / Cookie 内容。")

        sec_user_id = extract_sec_user_id_from_curl(curl_text)
        author_url = extract_author_url_from_curl(curl_text)
        if not sec_user_id and author_url:
            sec_user_id = extract_sec_user_id(author_url)
        if not sec_user_id:
            raise ValueError("无法从当前输入中提取 sec_user_id，请检查 URL / cURL / Cookie 内容。")

        return DownloadTarget(
            kind="user",
            identifier=sec_user_id,
            source_url=author_url or "",
            resolved_url=author_url or "",
        )

    def run_cli_download(self, request: DownloadRequest, log_callback=None) -> None:
        save_dir = self._ensure_save_dir(request.save_dir)
        cookie_manager = self._build_cookie_manager(request)
        api_client = DouyinAPIClient(
            cookie_manager,
            error_callback=lambda error: self._emit_log(log_callback, f"API错误: {error}"),
        )
        downloader = Downloader(api_client, save_dir)
        target = self.resolve_target(request, api_client=api_client)

        self._emit_target_logs(request, target, save_dir, log_callback)
        self._run_download_target(api_client, downloader, target, log_callback=log_callback)

    def run_gui_download(self, request: DownloadRequest, callbacks: DownloadCallbacks) -> None:
        if self.gui_downloader_factory is None:
            from douyin_downloader.gui.downloader import GUIDownloader

            self.gui_downloader_factory = GUIDownloader

        save_dir = self._ensure_save_dir(request.save_dir)
        cookie_manager = self._build_cookie_manager(request)
        api_client = DouyinAPIClient(
            cookie_manager,
            error_callback=lambda error: self._emit_log(callbacks.log_callback, f"API错误: {error}"),
        )
        downloader = self.gui_downloader_factory(
            api_client=api_client,
            save_dir=save_dir,
            progress_callback=callbacks.progress_callback,
            error_callback=callbacks.error_callback,
            queue_init_callback=callbacks.queue_init_callback,
            queue_update_callback=callbacks.queue_update_callback,
        )
        target = self.resolve_target(request, api_client=api_client)

        self._emit_log(callbacks.log_callback, "下载任务开始执行...")
        self._emit_target_logs(request, target, save_dir, callbacks.log_callback)
        self._run_download_target(api_client, downloader, target, callbacks=callbacks)

    def _run_download_target(
        self,
        api_client: DouyinAPIClient,
        downloader,
        target: DownloadTarget,
        *,
        callbacks: DownloadCallbacks | None = None,
        log_callback=None,
    ) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if target.kind == "aweme":
                aweme_detail = api_client.get_aweme_detail(target.identifier, page_url=target.resolved_url or target.source_url)
                if not aweme_detail:
                    raise RuntimeError(api_client.last_error or f"未能获取作品 {target.identifier} 的详情信息")
                self._emit_log(
                    callbacks.log_callback if callbacks else log_callback,
                    f"识别为单作品下载，作品ID: {target.identifier}",
                )
                loop.run_until_complete(downloader.download_aweme(aweme_detail))
            else:
                self._emit_log(
                    callbacks.log_callback if callbacks else log_callback,
                    f"识别为作者主页下载，sec_user_id: {target.identifier}",
                )
                loop.run_until_complete(downloader.download_user_posts(target.identifier))

            failure_reports = downloader.export_failed_entries()
            self._emit_download_summary(downloader, failure_reports, callbacks=callbacks, log_callback=log_callback)
        finally:
            loop.close()

    def _emit_target_logs(self, request: DownloadRequest, target: DownloadTarget, save_dir: Path, log_callback) -> None:
        self._emit_log(log_callback, f"保存目录: {save_dir}")
        if request.url.strip():
            self._emit_log(log_callback, f"输入内容: {request.url.strip()}")
        if request.curl_file:
            self._emit_log(log_callback, f"已导入 cURL 文件: {request.curl_file}")
        if request.curl_text.strip():
            self._emit_log(log_callback, f"已接收认证文本输入（{len(request.curl_text.strip())} 个字符）")
        if target.source_url:
            self._emit_log(log_callback, f"原始链接: {target.source_url}")
        if target.resolved_url and target.resolved_url != target.source_url:
            self._emit_log(log_callback, f"解析后链接: {target.resolved_url}")

    def _emit_download_summary(self, downloader, failure_reports, *, callbacks: DownloadCallbacks | None, log_callback) -> None:
        callback = callbacks.log_callback if callbacks else log_callback
        stats = getattr(downloader, "download_stats", None)
        if isinstance(stats, dict):
            self._emit_log(
                callback,
                f"下载任务结束: 成功 {stats.get('completed', 0)}，失败 {stats.get('failed', 0)}，跳过 {stats.get('skipped', 0)}。",
            )
            if stats.get("failed", 0) > 0:
                self._emit_log(callback, "部分资源下载失败；如果失败项出现 403/429，通常表示触发了频率风控。")
        else:
            self._emit_log(callback, "下载任务结束。")

        if failure_reports:
            self._emit_log(callback, f"失败清单: {failure_reports[0]}")
            self._emit_log(callback, f"失败文本清单: {failure_reports[1]}")

    def _build_cookie_manager(self, request: DownloadRequest) -> CookieManager:
        return CookieManager(
            curl_file=request.curl_file,
            curl_text=request.curl_text.strip() or None,
        )

    def _ensure_save_dir(self, save_dir: Path | str) -> Path:
        save_path = Path(save_dir).expanduser()
        save_path.mkdir(parents=True, exist_ok=True)
        return save_path

    def _resolve_curl_text(self, request: DownloadRequest) -> str:
        inline_text = request.curl_text.strip()
        if inline_text:
            return inline_text
        if request.curl_file:
            try:
                return read_curl_text(request.curl_file)
            except FileNotFoundError:
                return ""
        return ""

    @staticmethod
    def _emit_log(log_callback, message: str) -> None:
        if log_callback:
            log_callback(message)
