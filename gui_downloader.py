"""
GUI专用的下载器类，支持进度回调
"""
import asyncio
import time
from typing import Callable, Optional
from pathlib import Path
import aiohttp
from douyin_downloader.downloader.downloader import Downloader


class GUIDownloader(Downloader):
    """GUI专用的下载器，支持进度回调和错误处理"""
    
    def __init__(self, 
                 output_dir: str = "downloads",
                 max_retries: int = 3,
                 progress_callback: Optional[Callable] = None,
                 error_callback: Optional[Callable] = None,
                 queue_init_callback: Optional[Callable] = None,
                 queue_update_callback: Optional[Callable] = None):
        super().__init__(output_dir, max_retries)
        self.progress_callback = progress_callback
        self.error_callback = error_callback
        self.queue_init_callback = queue_init_callback
        self.queue_update_callback = queue_update_callback
        self.download_stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': time.time(),
            'errors': []  # 存储错误信息
        }
        self.current_downloads = {}  # 存储每个文件的下载状态
    
    async def _download_item(self, item: dict):
        """
        下载单个作品，支持进度回调
        """
        video = item.get('video')
        if not video:
            self._update_stats('skipped', file_info=f"作品 {item.get('aweme_id')} 没有视频数据")
            return

        # 优先选择 1080p 视频源
        video_url = self._get_highest_quality_url(video)

        if not video_url:
            self._update_stats('skipped', file_info=f"作品 {item.get('aweme_id')} 无有效链接")
            return

        video_id = item['aweme_id']
        desc = item.get('desc', 'no_desc')
        
        # 清理描述文本，使其成为有效的文件名
        valid_desc = "".join(c for c in desc if c.isalnum() or c in (' ', '_')).rstrip()
        filename = f"{valid_desc}_{video_id}.mp4"
        filepath = self.save_dir / filename

        if filepath.exists():
            self._update_stats('skipped', file_info=f"文件已存在: {filename}")
            return

        self._update_stats('start', filename=filename, video_url=video_url)
        
        try:
            headers = self.api_client._get_headers()
            if self.current_sec_user_id:
                headers['referer'] = f'https://www.douyin.com/user/{self.current_sec_user_id}'

            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(video_url) as response:
                    response.raise_for_status()
                    
                    # 获取文件大小
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    with open(filepath, 'wb') as f:
                        start_time = time.time()
                        
                        while True:
                            chunk = await response.content.read(8192)  # 8KB chunks
                            if not chunk:
                                break
                            
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # 计算下载速度和进度
                            elapsed_time = time.time() - start_time
                            download_speed = downloaded_size / elapsed_time if elapsed_time > 0 else 0
                            
                            progress = (downloaded_size / total_size * 100) if total_size > 0 else 0
                            
                            self._update_stats('progress', 
                                              filename=filename,
                                              progress=progress,
                                              downloaded_size=downloaded_size,
                                              total_size=total_size,
                                              download_speed=download_speed)
            
            self._update_stats('completed', filename=filename, file_info=f"下载成功: {filename}")
            
        except (aiohttp.ClientError, KeyError, IndexError) as e:
            self._update_stats('failed', filename=filename, file_info=f"下载失败: {filename}, 错误: {e}", error=str(e))
            # 删除不完整的文件
            if filepath.exists():
                filepath.unlink()
    
    def _update_stats(self, event_type: str, **kwargs):
        """更新下载统计信息并触发回调"""
        filename = kwargs.get('filename', '')
        
        if event_type == 'start':
            self.download_stats['total'] += 1
            # 初始化当前文件的下载状态
            self.current_downloads[filename] = {
                'progress': 0,
                'speed': 0,
                'start_time': time.time()
            }
            
            # 更新队列状态为"下载中"
            if self.queue_update_callback:
                self.queue_update_callback(filename, "下载中", "0%", "-", "-", "-")
        
        elif event_type == 'progress':
            # 更新当前文件的进度状态
            if filename in self.current_downloads:
                self.current_downloads[filename]['progress'] = kwargs.get('progress', 0)
                self.current_downloads[filename]['speed'] = kwargs.get('download_speed', 0)
            
            # 更新队列进度和速度
            if self.queue_update_callback:
                progress_text = f"{kwargs.get('progress', 0):.1f}%"
                speed_text = f"{kwargs.get('download_speed', 0) / 1024:.1f}KB/s"
                size_text = f"{kwargs.get('downloaded_size', 0) / 1024 / 1024:.1f}MB" if 'downloaded_size' in kwargs else "-"
                self.queue_update_callback(filename, "下载中", progress_text, speed_text, size_text, "-")
        
        elif event_type == 'completed':
            self.download_stats['completed'] += 1
            # 移除完成的文件状态
            if filename in self.current_downloads:
                del self.current_downloads[filename]
            
            # 更新队列状态为"已完成"
            if self.queue_update_callback:
                self.queue_update_callback(filename, "已完成", "100%", "-", "-", "-")
        
        elif event_type == 'failed':
            self.download_stats['failed'] += 1
            # 移除失败的文件状态
            if filename in self.current_downloads:
                del self.current_downloads[filename]
            
            # 更新队列状态为"错误"
            if self.queue_update_callback:
                error_msg = kwargs.get('error', '未知错误')
                self.queue_update_callback(filename, "错误", "0%", "-", "-", error_msg)
        
        elif event_type == 'skipped':
            self.download_stats['skipped'] += 1
            
            # 更新队列状态为"已跳过"
            if self.queue_update_callback:
                self.queue_update_callback(filename, "已跳过", "-", "-", "-", "-")
        
        # 触发进度回调
        if self.progress_callback:
            self.progress_callback(self.download_stats.copy())
    
    async def download_user_posts(self, sec_user_id: str):
        """
        下载指定用户的所有作品，支持进度跟踪
        """
        self.current_sec_user_id = sec_user_id
        self.download_stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0,
            'current_file': '',
            'current_progress': 0,
            'download_speed': 0,
            'start_time': time.time()
        }
        
        aweme_list = []
        max_cursor = 0
        has_more = True

        # 获取作品列表
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

        # 更新总任务数
        self.download_stats['total'] = len(aweme_list)
        if self.progress_callback:
            self.progress_callback(self.download_stats.copy())

        # 初始化下载队列（将文件信息添加到GUI队列中）
        if self.queue_init_callback:
            file_list = []
            for item in aweme_list:
                video = item.get('video')
                if video:
                    video_id = item['aweme_id']
                    desc = item.get('desc', 'no_desc')
                    # 清理描述文本，使其成为有效的文件名
                    valid_desc = "".join(c for c in desc if c.isalnum() or c in (' ', '_')).rstrip()
                    filename = f"{valid_desc}_{video_id}.mp4"
                    file_list.append(filename)
            
            # 调用队列初始化回调
            self.queue_init_callback(file_list)

        # 开始下载
        await self.queue_manager.download_batch(self._download_item, aweme_list)