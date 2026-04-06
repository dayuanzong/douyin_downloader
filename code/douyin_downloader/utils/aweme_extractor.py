from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse


URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
AWEME_PATH_PATTERNS = (
    re.compile(r"/(?:video|note)/(?P<aweme_id>\d+)", re.IGNORECASE),
    re.compile(r"/share/(?:video|note)/(?P<aweme_id>\d+)", re.IGNORECASE),
)
AWEME_QUERY_KEYS = ("modal_id", "aweme_id", "item_id")
TRAILING_URL_PUNCTUATION = "。，“”\"'`;；,!?！？)]】}>"


def extract_share_url(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""

    match = URL_PATTERN.search(stripped)
    if not match:
        return stripped
    return match.group(0).rstrip(TRAILING_URL_PUNCTUATION)


def extract_aweme_id(url_or_text: str) -> str | None:
    candidate = extract_share_url(url_or_text)
    if not candidate:
        return None

    parsed = urlparse(candidate)
    for pattern in AWEME_PATH_PATTERNS:
        match = pattern.search(parsed.path)
        if match:
            return match.group("aweme_id")

    query_values = parse_qs(parsed.query)
    for key in AWEME_QUERY_KEYS:
        values = query_values.get(key)
        if values and values[0].isdigit():
            return values[0]

    return None
