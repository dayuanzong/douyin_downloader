from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import threading

from douyin_downloader.paths import DOWNLOADS_DIR


@dataclass(slots=True)
class DownloadRequest:
    url: str = ""
    save_dir: Path = DOWNLOADS_DIR
    curl_text: str = ""
    curl_file: Path | None = None
    download_mode: str = "author"

    @property
    def has_auth_input(self) -> bool:
        return bool(self.url.strip() or self.curl_text.strip() or self.curl_file)


@dataclass(slots=True)
class DownloadCallbacks:
    progress_callback: Callable[[dict], None] | None = None
    error_callback: Callable[[dict], None] | None = None
    queue_init_callback: Callable[[list[str]], None] | None = None
    queue_update_callback: Callable[[str, str, str, str, str, str], None] | None = None
    log_callback: Callable[[str], None] | None = None
    cancel_event: threading.Event | None = None


@dataclass(slots=True)
class DownloadTarget:
    kind: str
    identifier: str
    source_url: str = ""
    resolved_url: str = ""
