#!/usr/bin/env python3
"""
增强下载器 - 支持Cookie、Cloudflare绕过和更好的错误处理
"""
import asyncio
import aiohttp
import aiofiles
import os
import json
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from dataclasses import dataclass

from config import Config
from video_extractor import VideoInfo


@dataclass
class DownloadResult:
    """下载结果"""
    url: str
    filename: str
    success: bool
    error: Optional[str] = None
    file_size: int = 0
    duration: float = 0.0


class EnhancedDownloader:
    """增强下载器"""
    
    def __init__(self, config: Config):
        """初始化"""
        self.config = config
        self.session: aiohttp.ClientSession = None
        self.cookies = {}
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.create_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close_session()
    
    async def load_cookies(self, cookie_file: str = "raw_cookies.json"):
        """加载Cookie文件"""
        try:
            if os.path.exists(cookie_file):
                with open(cookie_file, 'r', encoding='utf-8') as f:
                    cookies_data = json.load(f)
                
                # 转换为aiohttp可用的字典格式
                for cookie in cookies_data:
                    if 'name' in cookie and 'value' in cookie:
                        self.cookies[cookie['name']] = cookie['value']
                
                print(f"已加载 {len(self.cookies)} 个Cookie")
                return True
            else:
                print(f"Cookie文件不存在: {cookie_file}")
        except Exception as e:
            print(f"加载Cookie失败: {e}")
        
        return False
    
    async def create_session(self):
        """创建aiohttp会话，包含Cookie和增强的请求头"""
        # 基础请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        # 更新用户自定义配置
        if hasattr(self.config, 'headers'):
            headers.update(self.config.headers)
        
        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout,
            connect=30,
            sock_read=60
        )
        
        connector = aiohttp.TCPConnector(
            limit=self.config.max_concurrent,
            ssl=False
        )
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            cookies=self.cookies,
            timeout=timeout,
            connector=connector
        )
    
    async def close_session(self):
        """关闭会话"""
        if self.session:
            await self.session.close()
    
    def get_filename(self, url: str, title: str = "") -> str:
        """生成文件名"""
        parsed = urlparse(url)
        path = parsed.path
        
        # 提取原始文件名
        original_filename = os.path.basename(path)
        
        # 如果原始文件名有效，使用它
        if original_filename and '.' in original_filename and len(original_filename) > 5:
            base_name = original_filename
        else:
            # 使用标题或生成哈希
            if title:
                # 清理标题中的非法字符
                import re
                safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
                base_name = safe_title[:50]
            else:
                import hashlib
                url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
                base_name = f"video_{url_hash}"
            
            # 添加扩展名
            # 从URL或Content-Type推断扩展名
            if '.mp4' in url.lower():
                base_name += '.mp4'
            elif '.webm' in url.lower():
                base_name += '.webm'
            elif '.avi' in url.lower():
                base_name += '.avi'
            elif '.mov' in url.lower():
                base_name += '.mov'
            elif '.mkv' in url.lower():
                base_name += '.mkv'
            else:
                base_name += '.mp4'  # 默认
        
        return base_name
    
    async def download_file(self, url: str, title: str = "") -> DownloadResult:
        """下载单个文件"""
        filename = self.get_filename(url, title)
        filepath = os.path.join(self.config.download_dir, filename)
        
        # 确保下载目录存在
        os.makedirs(self.config.download_dir, exist_ok=True)
        
        # 如果文件已存在，检查大小是否完整
        if os.path.exists(filepath):
            print(f"文件已存在: {filename}")
            return DownloadResult(
                url=url,
                filename=filename,
                success=True,
                file_size=os.path.getsize(filepath)
            )
        
        print(f"正在下载: {filename} ({title})")
        
        for attempt in range(self.config.max_retries):
            try:
                async with self.session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        
                        # 获取内容类型
                        content_type = response.headers.get('content-type', '')
                        
                        # 如果是视频流，可能需要特殊处理
                        is_video = 'video' in content_type.lower() or any(ext in url.lower() for ext in ['.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv'])
                        
                        async with aiofiles.open(filepath, 'wb') as f:
                            async for chunk in response.content.iter_chunked(self.config.chunk_size):
                                await f.write(chunk)
                                downloaded += len(chunk)
                                
                                # 显示进度
                                if total_size > 0:
                                    percent = (downloaded / total_size) * 100
                                    print(f"  {filename}: {percent:.1f}% ({downloaded}/{total_size} bytes)", end='\r')
                                elif is_video:
                                    print(f"  {filename}: 已下载 {downloaded} 字节", end='\r')
                        
                        print(f"  {filename}: 下载完成 ({downloaded} 字节)")
                        
                        return DownloadResult(
                            url=url,
                            filename=filename,
                            success=True,
                            file_size=downloaded
                        )
                    else:
                        error_msg = f"HTTP错误 {response.status}"
                        print(f"  {filename}: {error_msg}")
                        
                        # 如果是403，可能需要更新Cookie
                        if response.status == 403:
                            print(f"  {filename}: 访问被拒绝，可能需要更新Cookie")
                        
                        return DownloadResult(
                            url=url,
                            filename=filename,
                            success=False,
                            error=error_msg
                        )
                        
            except aiohttp.ClientError as e:
                error_msg = f"网络错误: {e}"
                print(f"  {filename}: 下载失败 (尝试 {attempt + 1}/{self.config.max_retries}): {error_msg}")
                
                if attempt < self.config.max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"  {filename}: 等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    return DownloadResult(
                        url=url,
                        filename=filename,
                        success=False,
                        error=error_msg
                    )
            except Exception as e:
                error_msg = f"未知错误: {e}"
                print(f"  {filename}: {error_msg}")
                return DownloadResult(
                    url=url,
                    filename=filename,
                    success=False,
                    error=error_msg
                )
        
        return DownloadResult(
            url=url,
            filename=filename,
            success=False,
            error="达到最大重试次数"
        )
    
    async def download_all(self, urls: List[str], titles: Optional[List[str]] = None) -> List[DownloadResult]:
        """并发下载所有文件"""
        if not self.session:
            await self.create_session()
        
        if titles is None:
            titles = [""] * len(urls)
        
        print(f"开始下载 {len(urls)} 个文件...")
        
        # 创建信号量控制并发数
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def download_with_semaphore(url: str, title: str):
            async with semaphore:
                return await self.download_file(url, title)
        
        # 并发下载
        tasks = [download_with_semaphore(url, title) for url, title in zip(urls, titles)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(DownloadResult(
                    url=urls[i],
                    filename=self.get_filename(urls[i], titles[i] if i < len(titles) else ""),
                    success=False,
                    error=f"异常: {result}"
                ))
            else:
                final_results.append(result)
        
        # 统计结果
        success_count = sum(1 for r in final_results if r.success)
        failed_count = len(final_results) - success_count
        
        print(f"下载完成: {success_count} 成功, {failed_count} 失败")
        
        return final_results
    
    async def download_videos_from_extractor(self, extractor, url: str):
        """使用视频提取器下载视频"""
        # 导入VideoExtractor
        from video_extractor import VideoExtractor, VideoInfo
        
        print(f"使用视频提取器从 {url} 下载视频...")
        
        # 创建视频提取器实例
        async with VideoExtractor(headless=True) as ve:
            # 加载Cookie
            await ve.load_cookies()
            
            # 提取视频
            videos = await ve.extract_videos_from_page(url)
            
            if not videos:
                print("未找到视频")
                return []
            
            print(f"找到 {len(videos)} 个视频")
            
            # 选择最佳视频（按分辨率和文件大小）
            best_videos = self._select_best_videos(videos)
            
            # 下载视频
            urls = [video.url for video in best_videos]
            titles = [video.title for video in best_videos]
            
            results = await self.download_all(urls, titles)
            
            return results
    
    def _select_best_videos(self, videos: List[VideoInfo], max_count: int = 3) -> List[VideoInfo]:
        """选择最佳视频"""
        if not videos:
            return []
        
        # 过滤广告视频
        non_ad_videos = [v for v in videos if not v.is_ad_video]
        
        if not non_ad_videos:
            non_ad_videos = videos
        
        # 按分辨率和文件大小排序
        def sort_key(video: VideoInfo):
            # 解析分辨率
            width, height = 0, 0
            if video.resolution and 'x' in video.resolution:
                try:
                    parts = video.resolution.split('x')
                    width = int(parts[0])
                    height = int(parts[1])
                except:
                    pass
            
            # 优先考虑分辨率高、文件大小大的视频
            return (width * height, video.file_size)
        
        sorted_videos = sorted(non_ad_videos, key=sort_key, reverse=True)
        
        return sorted_videos[:max_count]


async def test_enhanced_downloader():
    """测试增强下载器"""
    from config import Config
    
    config = Config()
    config.download_dir = "test_downloads"
    config.max_concurrent = 2
    config.max_retries = 3
    config.timeout = 30
    config.chunk_size = 8192
    
    async with EnhancedDownloader(config) as downloader:
        # 加载Cookie
        await downloader.load_cookies("raw_cookies.json")
        
        # 测试下载
        test_urls = [
            "https://example.com/video1.mp4",
            "https://example.com/video2.mp4",
        ]
        
        results = await downloader.download_all(test_urls)
        
        for result in results:
            print(f"{result.filename}: {'成功' if result.success else '失败'} - {result.error}")


if __name__ == "__main__":
    asyncio.run(test_enhanced_downloader())
