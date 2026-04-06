from __future__ import annotations

import re
from pathlib import Path

from douyin_downloader.cookies.parser import extract_cookie_from_curl, read_curl_text


CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


class CookieManager:
    def __init__(self, curl_file: Path | None = None, curl_text: str | None = None):
        self.curl_file = curl_file
        self.curl_text = curl_text
        self._cookie = None
        self._last_mtime = 0
        self._last_inline_text = curl_text or ""

    def _is_file_updated(self) -> bool:
        if self.curl_text is not None:
            updated = self.curl_text != self._last_inline_text
            self._last_inline_text = self.curl_text
            return updated

        if self.curl_file is None:
            return False

        try:
            mtime = self.curl_file.stat().st_mtime
            if mtime > self._last_mtime:
                self._last_mtime = mtime
                return True
            return False
        except FileNotFoundError:
            return True

    def _parse_cookie_from_curl(self) -> str | None:
        try:
            if self.curl_text is not None:
                curl_command = self.curl_text
            elif self.curl_file is not None:
                curl_command = read_curl_text(self.curl_file)
            else:
                return None
            return extract_cookie_from_curl(curl_command)
        except FileNotFoundError:
            return None

    def get_cookie(self) -> str | None:
        if self._is_file_updated() or not self._cookie:
            self._cookie = self._sanitize_cookie_text(self._parse_cookie_from_curl())
        return self._cookie

    @staticmethod
    def _sanitize_cookie_text(cookie_text: str | None) -> str | None:
        if not cookie_text:
            return None

        pairs: list[str] = []
        seen_names: set[str] = set()
        for segment in cookie_text.split(";"):
            if "=" not in segment:
                continue
            name, value = segment.split("=", 1)
            clean_name = CONTROL_CHAR_PATTERN.sub("", name).replace("=", "").replace(";", "").strip()
            clean_value = CONTROL_CHAR_PATTERN.sub("", value).replace(";", "").strip()
            if not clean_name or not clean_value or clean_name in seen_names:
                continue
            seen_names.add(clean_name)
            pairs.append(f"{clean_name}={clean_value}")

        return "; ".join(pairs) or None
