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
from douyin_downloader.services.browser_auth_service import BrowserAuthService
from douyin_downloader.utils.aweme_extractor import extract_aweme_id, extract_share_url
from douyin_downloader.utils.sec_user_id_extractor import extract_sec_user_id


class DownloadService:
    def __init__(self, gui_downloader_factory=None, browser_auth_service: BrowserAuthService | None = None):
        self.gui_downloader_factory = gui_downloader_factory
        self.browser_auth_service = browser_auth_service or BrowserAuthService(
            preferred_executable=Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
        )

    def resolve_target(self, request: DownloadRequest, api_client: DouyinAPIClient | None = None) -> DownloadTarget:
        requested_mode = (request.download_mode or "author").strip().lower()
        url = extract_share_url(request.url.strip())
        if url:
            sec_user_id = extract_sec_user_id(url)
            direct_aweme_id = extract_aweme_id(url)

            if requested_mode == "author" and sec_user_id:
                return DownloadTarget(kind="user", identifier=sec_user_id, source_url=url, resolved_url=url)
            if requested_mode == "aweme" and direct_aweme_id:
                return DownloadTarget(kind="aweme", identifier=direct_aweme_id, source_url=url, resolved_url=url)
            if direct_aweme_id:
                return DownloadTarget(kind="aweme", identifier=direct_aweme_id, source_url=url, resolved_url=url)
            if sec_user_id:
                return DownloadTarget(kind="user", identifier=sec_user_id, source_url=url, resolved_url=url)

            resolved_url = api_client.resolve_url(url) if api_client else url
            resolved_sec_user_id = extract_sec_user_id(resolved_url)
            resolved_aweme_id = extract_aweme_id(resolved_url)

            if requested_mode == "author" and resolved_sec_user_id:
                return DownloadTarget(
                    kind="user",
                    identifier=resolved_sec_user_id,
                    source_url=url,
                    resolved_url=resolved_url,
                )
            if requested_mode == "aweme" and resolved_aweme_id:
                return DownloadTarget(
                    kind="aweme",
                    identifier=resolved_aweme_id,
                    source_url=url,
                    resolved_url=resolved_url,
                )
            if resolved_aweme_id:
                return DownloadTarget(
                    kind="aweme",
                    identifier=resolved_aweme_id,
                    source_url=url,
                    resolved_url=resolved_url,
                )
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
            raise ValueError("Unable to resolve the target from the current URL or authentication text.")

        sec_user_id = extract_sec_user_id_from_curl(curl_text)
        author_url = extract_author_url_from_curl(curl_text)
        if not sec_user_id and author_url:
            sec_user_id = extract_sec_user_id(author_url)
        if not sec_user_id:
            raise ValueError("Unable to extract sec_user_id from the current URL or authentication text.")

        return DownloadTarget(
            kind="user",
            identifier=sec_user_id,
            source_url=author_url or "",
            resolved_url=author_url or "",
        )

    def run_cli_download(self, request: DownloadRequest, log_callback=None) -> None:
        save_dir = self._ensure_save_dir(request.save_dir)
        cookie_manager = self._build_cookie_manager(request, log_callback=log_callback)
        api_client = DouyinAPIClient(
            cookie_manager,
            error_callback=lambda error: self._emit_log(log_callback, f"API error: {error}"),
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
        cookie_manager = self._build_cookie_manager(request, log_callback=callbacks.log_callback)
        api_client = DouyinAPIClient(
            cookie_manager,
            error_callback=lambda error: self._emit_log(callbacks.log_callback, f"API error: {error}"),
        )
        downloader = self.gui_downloader_factory(
            api_client=api_client,
            save_dir=save_dir,
            cancel_event=callbacks.cancel_event,
            progress_callback=callbacks.progress_callback,
            error_callback=callbacks.error_callback,
            queue_init_callback=callbacks.queue_init_callback,
            queue_update_callback=callbacks.queue_update_callback,
        )
        target = self.resolve_target(request, api_client=api_client)

        self._emit_log(callbacks.log_callback, "Download task started.")
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
                    raise RuntimeError(api_client.last_error or f"Unable to load aweme detail: {target.identifier}")
                self._emit_log(
                    callbacks.log_callback if callbacks else log_callback,
                    f"Detected single-aweme download: {target.identifier}",
                )
                loop.run_until_complete(downloader.download_aweme(aweme_detail))
            else:
                self._emit_log(
                    callbacks.log_callback if callbacks else log_callback,
                    f"Detected author download: {target.identifier}",
                )
                loop.run_until_complete(downloader.download_user_posts(target.identifier))

            failure_reports = downloader.export_failed_entries()
            self._emit_download_summary(downloader, failure_reports, callbacks=callbacks, log_callback=log_callback)
        finally:
            loop.close()

    def _emit_target_logs(self, request: DownloadRequest, target: DownloadTarget, save_dir: Path, log_callback) -> None:
        self._emit_log(log_callback, f"Save directory: {save_dir}")
        if request.url.strip():
            self._emit_log(log_callback, f"Input: {request.url.strip()}")
        if request.curl_file:
            self._emit_log(log_callback, f"Using cURL file: {request.curl_file}")
        if request.curl_text.strip():
            self._emit_log(log_callback, f"Using inline authentication text ({len(request.curl_text.strip())} chars)")
        if target.source_url:
            self._emit_log(log_callback, f"Source URL: {target.source_url}")
        if target.resolved_url and target.resolved_url != target.source_url:
            self._emit_log(log_callback, f"Resolved URL: {target.resolved_url}")

    def _emit_download_summary(self, downloader, failure_reports, *, callbacks: DownloadCallbacks | None, log_callback) -> None:
        callback = callbacks.log_callback if callbacks else log_callback
        stats = getattr(downloader, "download_stats", None)
        if isinstance(stats, dict):
            self._emit_log(
                callback,
                f"Download finished: success {stats.get('completed', 0)}, failed {stats.get('failed', 0)}, skipped {stats.get('skipped', 0)}.",
            )
        else:
            self._emit_log(callback, "Download finished.")

        if failure_reports:
            self._emit_log(callback, f"Failed entries CSV: {failure_reports[0]}")
            self._emit_log(callback, f"Failed entries TXT: {failure_reports[1]}")

    def _build_cookie_manager(self, request: DownloadRequest, log_callback=None) -> CookieManager:
        inline_text = request.curl_text.strip()
        if inline_text:
            self._emit_log(log_callback, "Refreshing the managed browser profile from inline authentication text.")
            imported = self.browser_auth_service.import_cookie_text(
                bootstrap_cookie_text=inline_text,
                log_callback=log_callback,
            )
            return CookieManager(curl_text=imported.cookie_text)

        if request.curl_file:
            try:
                file_text = read_curl_text(request.curl_file).strip()
            except FileNotFoundError:
                file_text = ""
            if file_text:
                self._emit_log(log_callback, "Refreshing the managed browser profile from the cURL file.")
                imported = self.browser_auth_service.import_cookie_text(
                    bootstrap_cookie_text=file_text,
                    log_callback=log_callback,
                )
                return CookieManager(curl_text=imported.cookie_text)

        self._emit_log(log_callback, "Trying managed browser authentication.")
        imported = self.browser_auth_service.import_cookie_text(log_callback=log_callback)
        return CookieManager(curl_text=imported.cookie_text)

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
