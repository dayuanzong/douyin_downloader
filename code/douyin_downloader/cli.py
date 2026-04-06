from __future__ import annotations

import argparse
from pathlib import Path

from douyin_downloader.models import DownloadRequest
from douyin_downloader.paths import DOWNLOADS_DIR
from douyin_downloader.services.download_service import DownloadService


def _prompt_for_text(label: str) -> str:
    while True:
        try:
            value = input(f"{label}\n> ").strip()
        except EOFError:
            value = ""
        if value:
            return value
        print("输入不能为空，请重新输入。")


def main() -> None:
    parser = argparse.ArgumentParser(description="下载抖音作者主页内容或单个作品。")
    parser.add_argument("url", nargs="?", type=str, help="作者主页、单作品或分享短链 URL。")
    parser.add_argument("--save-dir", type=str, default=str(DOWNLOADS_DIR), help="媒体保存目录。")
    parser.add_argument("--curl-file", type=str, help="包含 cURL 命令的文本文件。")
    parser.add_argument("--curl-text", type=str, help="直接传入 cURL 文本。")
    args = parser.parse_args()

    request = DownloadRequest(
        url=(args.url or "").strip(),
        save_dir=Path(args.save_dir),
        curl_text=(args.curl_text or "").strip(),
        curl_file=Path(args.curl_file) if args.curl_file else None,
    )

    if not request.url and not request.curl_text and not request.curl_file:
        request.url = _prompt_for_text("请输入作者主页或作品链接，或使用 --curl-text / --curl-file 提供认证输入：")

    service = DownloadService()
    service.run_cli_download(request, log_callback=print)
