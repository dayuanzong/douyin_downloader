
import argparse
import asyncio
from pathlib import Path
import re
from typing import Optional

from douyin_downloader.api.client import DouyinAPIClient
from douyin_downloader.cookies.manager import CookieManager
from douyin_downloader.downloader.downloader import Downloader


def extract_url_from_curl(curl_file: Path) -> Optional[str]:
    """
    从 cURL 文件中提取作者主页 URL。
    
    :param curl_file: cURL 文件路径
    :return: 提取出的 URL，如果未找到则返回 None
    """
    try:
        content = curl_file.read_text(encoding='utf-8')
        # 匹配 URL 模式
        if match := re.search(r'https://www\.douyin\.com/user/[\w.-]+', content):
            return match[0]
        # 匹配 sec_user_id 参数模式
        if match := re.search(r'https://[^\s]*sec_user_id=[\w-]+', content):
            return match[0]
    except Exception as e:
        print(f"读取 cURL 文件时出错: {e}")
    
    return None

def extract_sec_user_id(url: str) -> str | None:
    """
    从 URL 中提取 sec_user_id。

    :param url: 作者主页的 URL。
    :return: 提取出的 sec_user_id，如果未找到则返回 None。
    """
    # 优先匹配路径中的 ID
    if match := re.search(r"/user/([\w.-]+)", url):
        return match[1]
    # 其次匹配 sec_user_id 参数
    if match := re.search(r"sec_user_id=([\w-]+)", url):
        return match[1]
    # 兼容旧的 sec_uid
    if match := re.search(r"sec_uid=([\w-]+)", url):
        return match[1]
    # 如果上面没有匹配到，尝试从重定向后的 URL 中查找
    try:
        import requests
        response = requests.get(url, allow_redirects=True)
        if match := re.search(r"sec_user_id=([\w-]+)", response.url):
            return match[1]
    except requests.RequestException:
        pass
    return None

def _prompt_for_url() -> str:
    """
    交互式提示用户输入抖音作者主页 URL。

    :return: 用户输入的非空 URL 字符串。
    """
    while True:
        try:
            url = input("请输入抖音作者主页 URL：\n> ").strip()
        except EOFError:
            url = ""
        if url:
            return url
        print("URL 不能为空，请重新输入。")


def main():
    """
    主函数，用于解析参数和启动下载器。
    """
    parser = argparse.ArgumentParser(description='下载指定抖音作者的所有作品。')
    # 将 url 设置为可选的定位参数；缺省时进入交互式输入
    parser.add_argument('url', nargs='?', type=str, help='作者主页的 URL（留空则进入交互输入）。')
    parser.add_argument('--save-dir', type=str, default='downloads', help='视频保存目录。')
    parser.add_argument('--curl-file', type=str, default='samples/cURL.txt', help='包含 cURL 命令的文件的路径。')
    args = parser.parse_args()

    # 以脚本所在目录为基准，增强相对路径解析
    repo_root = Path(__file__).resolve().parent

    # 解析 cURL 文件路径：
    # 1) 直接按用户传入解析；
    # 2) 若不存在且为相对路径，则以脚本目录作为基准；
    # 3) 仍不存在则回退到脚本目录下的 samples/cURL.txt
    curl_file = Path(args.curl_file)
    if not curl_file.exists():
        if not curl_file.is_absolute():
            candidate = repo_root / curl_file
            if candidate.exists():
                curl_file = candidate
            else:
                fallback = repo_root / 'samples' / 'cURL.txt'
                curl_file = fallback
        else:
            fallback = repo_root / 'samples' / 'cURL.txt'
            curl_file = fallback

    # 若仍未找到 cURL 文件，则交互式提示用户输入路径
    if not curl_file.exists():
        print(f"cURL 文件未找到: {curl_file}")
        print("请输入 cURL.txt 的完整路径，或直接回车使用默认 samples/cURL.txt：")
        try:
            user_path = input("> ").strip()
        except EOFError:
            user_path = ""
        if user_path:
            curl_file = Path(user_path)
        else:
            curl_file = repo_root / 'samples' / 'cURL.txt'
        if not curl_file.exists():
            print("仍未找到 cURL 文件，请检查路径后重试。")
            return

    # 若未提供 URL，尝试从 cURL 文件中自动提取
    if not args.url:
        # 先尝试从 cURL 文件中提取 URL
        extracted_url = extract_url_from_curl(curl_file)
        if extracted_url:
            print(f"从 cURL 文件中自动提取到作者主页 URL: {extracted_url}")
            args.url = extracted_url
        else:
            # 如果无法自动提取，则交互式提示输入
            args.url = _prompt_for_url()

    sec_user_id = extract_sec_user_id(args.url)
    if not sec_user_id:
        print("无法从 URL 中提取 sec_user_id。请确保 URL 是有效的作者主页链接。")
        return

    print(f"成功提取 sec_user_id: {sec_user_id}")

    # 解析保存目录：优先使用用户传入；如为相对路径则相对脚本目录
    save_dir = Path(args.save_dir)
    if not save_dir.is_absolute():
        save_dir = repo_root / save_dir

    # 确保保存目录存在
    save_dir.mkdir(parents=True, exist_ok=True)

    cookie_manager = CookieManager(curl_file)
    api_client = DouyinAPIClient(cookie_manager)
    downloader = Downloader(api_client, save_dir)

    print(f"开始下载用户 {sec_user_id} 的所有作品...")
    # 正确运行异步下载协程
    asyncio.run(downloader.download_user_posts(sec_user_id))
    print("所有任务已完成。")

if __name__ == "__main__":
    main()

