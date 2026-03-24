
import asyncio
import aiohttp
from pathlib import Path
import requests

from ..api.client import DouyinAPIClient
from .queue_manager import QueueManager

class Downloader:
    def __init__(self, api_client: DouyinAPIClient, save_dir: Path, max_workers: int = 5):
        self.api_client = api_client
        self.save_dir = save_dir
        self.queue_manager = QueueManager(max_workers)
        self.current_sec_user_id = None

    async def _download_item(self, item: dict):
        """
        下载单个作品。
        """
        video = item.get('video')
        if not video:
            print(f"作品 {item.get('aweme_id')} 没有视频数据，跳过下载。")
            return

        # 优先选择 1080p 视频源
        video_url = self._get_highest_quality_url(video)

        if not video_url:
            print(f"无法找到作品 {item.get('aweme_id')} 的有效下载链接，跳过。")
            return

        print(f"准备下载: {video_url}")

        video_id = item['aweme_id']
        desc = item.get('desc', 'no_desc')

        # 清理描述文本，使其成为有效的文件名
        valid_desc = "".join(c for c in desc if c.isalnum() or c in (' ', '_')).rstrip()
        filename = f"{valid_desc}_{video_id}.mp4"
        filepath = self.save_dir / filename

        if filepath.exists():
            print(f"文件已存在: {filename}")
            return

        try:
            headers = self.api_client._get_headers()
            if self.current_sec_user_id:
                headers['referer'] = f'https://www.douyin.com/user/{self.current_sec_user_id}'

            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(video_url) as response:
                    response.raise_for_status()
                    with open(filepath, 'wb') as f:
                        while True:
                            chunk = await response.content.read(1024)
                            if not chunk:
                                break
                            f.write(chunk)
            print(f"下载成功: {filename}")
        except (aiohttp.ClientError, KeyError, IndexError) as e:
            print(f"下载失败: {filename}, 错误: {e}")
            # 可选择删除不完整的文件
            if filepath.exists():
                filepath.unlink()

    def _get_highest_quality_url(self, video: dict) -> str | None:
        """
        从视频数据中提取最高清晰度的视频 URL。
        优先寻找 1080p，其次是默认的 play_addr。
        """
        # 尝试从 h264 编码中寻找 1080p 链接
        if 'play_addr_h264' in video and video['play_addr_h264']:
            h264_urls = video['play_addr_h264'].get('url_list', [])
            for url in h264_urls:
                if 'video_1080p' in url:
                    return url

        # 如果没有 1080p，则使用默认的 play_addr
        if 'play_addr' in video and video['play_addr']:
            play_urls = video['play_addr'].get('url_list', [])
            if play_urls:
                return play_urls[0]

        return None

    async def download_user_posts(self, sec_user_id: str):
        """
        下载指定用户的所有作品。
        """
        self.current_sec_user_id = sec_user_id
        aweme_list = []
        max_cursor = 0
        has_more = True

        print("正在获取所有作品列表...")
        while has_more:
            data = self.api_client.get_user_posts(sec_user_id, max_cursor)
            if not data:
                break

            aweme_items = data.get('aweme_list', [])
            if not aweme_items:
                break

            aweme_list.extend(aweme_items)
            has_more = data.get('has_more', False)
            max_cursor = data.get('max_cursor', 0)
            print(f"已获取 {len(aweme_list)} 个作品...", end="\r")

        print(f"\n共获取到 {len(aweme_list)} 个作品，开始并行下载...")

        await self.queue_manager.download_batch(self._download_item, aweme_list)