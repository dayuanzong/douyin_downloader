from __future__ import annotations

import re
from pathlib import Path

from douyin_downloader.utils.sec_user_id_extractor import extract_sec_user_id

AUTHOR_URL_PATTERN = re.compile(r"https://www\.douyin\.com/user/[^\s'\"\\^]+")
SEC_USER_ID_PATTERN = re.compile(r"sec_user_id=([^&\s\"'^]+)")
SEC_UID_PATTERN = re.compile(r"sec_uid=([^&\s\"'^]+)")
COOKIE_INLINE_PATTERN = re.compile(
    r"(?:^|\s)(?:-b|--cookie)\s+(?P<value>\^?\".*?\^?\"|'.*?'|[^\r\n]+)",
    re.MULTILINE,
)
COOKIE_HEADER_PATTERN = re.compile(r"cookie\s*:\s*(?P<value>.+)", re.IGNORECASE)


def read_curl_text(curl_file: Path | None) -> str:
    if curl_file is None:
        return ""
    return curl_file.read_text(encoding="utf-8")


def normalize_curl_value(value: str) -> str:
    cleaned = value.strip().rstrip("\\").rstrip("^").strip()
    quote_pairs = (('^"', '"'), ('"', '"'), ("'", "'"))
    for start, end in quote_pairs:
        if cleaned.startswith(start) and cleaned.endswith(end):
            cleaned = cleaned[len(start): len(cleaned) - len(end)]
            break
    return cleaned.replace("^", "").strip()


def extract_cookie_from_curl(curl_text: str) -> str | None:
    stripped_text = curl_text.strip()
    if not stripped_text:
        return None

    for line in stripped_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-b") or stripped.startswith("--cookie"):
            parts = stripped.split(" ", 1)
            if len(parts) == 2:
                cookie = normalize_curl_value(parts[1])
                if cookie:
                    return cookie

        header_match = COOKIE_HEADER_PATTERN.match(stripped)
        if header_match:
            cookie = normalize_curl_value(header_match.group("value"))
            if cookie:
                return cookie

    match = COOKIE_INLINE_PATTERN.search(stripped_text)
    if not match:
        if "=" in stripped_text and (";" in stripped_text or stripped_text.lower().startswith("cookie=")):
            return normalize_curl_value(stripped_text.removeprefix("cookie=").removeprefix("Cookie="))
        return None

    cookie = normalize_curl_value(match.group("value"))
    return cookie or None


def extract_author_url_from_curl(curl_text: str) -> str | None:
    match = AUTHOR_URL_PATTERN.search(curl_text)
    if not match:
        return None
    return match.group(0).replace("^", "")


def extract_sec_user_id_from_curl(curl_text: str) -> str | None:
    author_url = extract_author_url_from_curl(curl_text)
    if author_url:
        extracted = extract_sec_user_id(author_url)
        if extracted:
            return extracted

    for pattern in (SEC_USER_ID_PATTERN, SEC_UID_PATTERN):
        match = pattern.search(curl_text)
        if match:
            return match.group(1).replace("^", "")

    return None
