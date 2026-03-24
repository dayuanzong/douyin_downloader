
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from douyin_downloader.api.client import DouyinAPIClient
from douyin_downloader.cookies.manager import CookieManager
from douyin_downloader.downloader.downloader import Downloader
from douyin_downloader.utils.sec_user_id_extractor import extract_sec_user_id

async def main():
    """
    主函数，用于启动下载器。
    """
    # 配置文件和目录
    curl_file = Path('samples/cURL.txt')
    download_dir = Path('downloads')
    download_dir.mkdir(exist_ok=True)

    # 初始化组件
    cookie_manager = CookieManager(curl_file)
    api_client = DouyinAPIClient(cookie_manager, error_callback=lambda error: print(f"API错误: {error}"))
    downloader = Downloader(api_client, download_dir)

    # 获取用户输入
    user_url = input("请输入作者主页链接: ")

    # 提取 sec_user_id
    sec_user_id = extract_sec_user_id(user_url)
    if not sec_user_id:
        print("无法从链接中提取 sec_user_id，请检查链接是否正确。")
        return

    print(f"成功提取 sec_user_id: {sec_user_id}")
    print(f"开始下载该作者的所有作品，将保存到 {download_dir.resolve()} 目录...")

    # 下载所有作品
    await downloader.download_user_posts(sec_user_id)

    print("所有作品下载完成。")

if __name__ == "__main__":
    asyncio.run(main())

