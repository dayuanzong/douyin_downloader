from __future__ import annotations

from pathlib import Path

from douyin_downloader.paths import CODE_DIR, COOKIE_GUIDE_FILE, CURL_TEMPLATE_FILE, DOWNLOADS_DIR, RUNTIME_DIR


def check_paths() -> None:
    print("=== 目录检查 ===")
    for path in (CODE_DIR, DOWNLOADS_DIR, RUNTIME_DIR):
        print(f"{path}: {'存在' if path.exists() else '缺失'}")

    print("\n=== 文件检查 ===")
    for path in (
        CODE_DIR / "gui_app.py",
        CODE_DIR / "main.py",
        COOKIE_GUIDE_FILE,
        CURL_TEMPLATE_FILE,
        CODE_DIR / "douyin_downloader" / "gui" / "app.py",
        CODE_DIR / "douyin_downloader" / "gui" / "controller.py",
    ):
        print(f"{path}: {'存在' if path.exists() else '缺失'}")


def main() -> None:
    check_paths()
    print("\n建议启动命令:")
    print("python code/gui_app.py")
    print("python code/main.py <分享链接>")


if __name__ == "__main__":
    main()
