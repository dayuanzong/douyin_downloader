from __future__ import annotations

import re

from douyin_downloader.paths import CURL_TEMPLATE_FILE


COOKIE_PATTERNS = (
    r'(?:-b|--cookie)\s+\^"([^\^"]+)\^"',
    r'(?:-b|--cookie)\s+["\']([^"\']+)["\']',
    r'(?:-b|--cookie)\s+([^\s]+)',
)


def main() -> None:
    curl_file_path = CURL_TEMPLATE_FILE
    print(f"读取文件: {curl_file_path}")
    if not curl_file_path.exists():
        print("未找到 cURL.txt，请先在项目根目录的 cURL.txt 中粘贴真实 cURL。")
        return

    curl_content = curl_file_path.read_text(encoding="utf-8").strip()
    print(f"文件内容长度: {len(curl_content)}")

    for index, pattern in enumerate(COOKIE_PATTERNS, start=1):
        match = re.search(pattern, curl_content, re.IGNORECASE)
        print(f"模式 {index}: {'命中' if match else '未命中'}")
        if not match:
            continue

        cookie_value = match.group(1).replace("^", "")
        print(f"Cookie 预览: {cookie_value[:200]}")
        for field in ("sessionid", "sid_tt", "sid_guard", "ttwid"):
            print(f"{field}: {'存在' if field in cookie_value else '缺失'}")
        break


if __name__ == "__main__":
    main()
