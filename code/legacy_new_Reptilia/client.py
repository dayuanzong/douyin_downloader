#!/usr/bin/env python3
"""
客户端类 - 处理HTTP请求和页面解析
"""
import asyncio
import aiohttp
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
import json

from config import Config
from cookie_manager import CookieManager

class VideoInfo:
    """视频信息类"""
    def __init__(self, url: str, title: str = "", resolution: str = "", file_size: int = 0):
        self.url = url
        self.title = title
        self.resolution = resolution
        self.file_size = file_size
        self.is_ad_video = False

class Ask4PornClient:
    """Ask4Porn客户端"""
    
    def __init__(self, config: Config):
        """初始化"""
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        from pathlib import Path
        self.cookie_manager = CookieManager(
            curl_file=Path(config.curl_file_path) if hasattr(config, 'curl_file_path') and config.curl_file_path else None,
            cookie_dict={'cf_clearance': config.cf_clearance} if config.cf_clearance else None
        )
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.create_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close_session()
    
    async def create_session(self):
        """创建aiohttp会话"""
        # 获取Cookie
        cookie_string = self.cookie_manager.get_cookie_string()
        
        headers = self.config.headers.copy()
        
        # 添加Cookie到请求头
        if cookie_string:
            headers['Cookie'] = cookie_string
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        connector = aiohttp.TCPConnector(limit=1)  # 限制并发数以避免被封
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            connector=connector
        )
    
    async def close_session(self):
        """关闭会话"""
        if self.session:
            await self.session.close()
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """获取页面内容"""
        if not self.session:
            await self.create_session()
        
        for attempt in range(self.config.max_retries):
            try:
                async with self.session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 403:
                        print(f"访问被拒绝 (403)，可能需要Cloudflare验证")
                        return None
                    else:
                        print(f"HTTP错误 {response.status}")
                        return None
            except aiohttp.ClientError as e:
                print(f"请求失败 (尝试 {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                
        return None
    
    async def get_video_info(self, url: str) -> Optional[VideoInfo]:
        """获取单个视频的信息"""
        html = await self.fetch_page(url)
        if not html:
            return None
        
        # 检查是否是Cloudflare挑战页面
        if 'Just a moment...' in html or 'cf-chl-bypass' in html:
            print("检测到Cloudflare挑战页面，需要手动处理")
            return None
        
        # 提取视频链接和相关信息
        video_info = await self._extract_video_info(html, url)
        if not video_info:
            print("未找到视频信息")
            return None
        
        # 获取视频文件大小
        video_info.file_size = await self._get_video_file_size(video_info.url)
        
        # 检查是否是广告视频
        video_info.is_ad_video = self._is_ad_video(video_info)
        
        print(f"找到视频: {video_info.url}")
        print(f"分辨率: {video_info.resolution}")
        print(f"文件大小: {video_info.file_size / 1024 / 1024:.2f} MB")
        print(f"是否为广告视频: {video_info.is_ad_video}")
        
        return video_info
    
    async def _extract_video_info(self, html: str, page_url: str) -> Optional[VideoInfo]:
        """从HTML中提取视频信息"""
        
        # 1. 查找JSON数据中的视频信息
        json_pattern = r'<script[^>]*type=["\']application/json["\'][^>]*>([^<]+)</script>'
        json_matches = re.findall(json_pattern, html, re.IGNORECASE | re.DOTALL)
        
        for json_str in json_matches:
            try:
                data = json.loads(json_str)
                video_info = self._parse_video_from_json(data, page_url)
                if video_info:
                    return video_info
            except json.JSONDecodeError:
                continue
        
        # 2. 查找video标签
        video_pattern = r'<video[^>]*>(.*?)</video>'
        video_matches = re.findall(video_pattern, html, re.IGNORECASE | re.DOTALL)
        
        for video_content in video_matches:
            video_info = self._parse_video_from_tag(video_content, page_url)
            if video_info:
                return video_info
        
        # 3. 查找source标签
        source_pattern = r'<source[^>]*>'
        source_matches = re.findall(source_pattern, html, re.IGNORECASE)
        
        for source_tag in source_matches:
            video_info = self._parse_video_from_source(source_tag, page_url)
            if video_info:
                return video_info
        
        # 4. 查找直接的视频URL
        direct_video_patterns = [
            r'["\']([^"\']+\.mp4[^"\']*)["\']',
            r'["\']([^"\']+\.webm[^"\']*)["\']',
            r'["\']([^"\']+\.m3u8[^"\']*)["\']',
        ]
        
        for pattern in direct_video_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                video_url = urljoin(page_url, match)
                return VideoInfo(
                    url=video_url,
                    title="未知标题",
                    resolution="未知",
                    file_size=0
                )
        
        return None
    
    def _parse_video_from_json(self, data: dict, page_url: str) -> Optional[VideoInfo]:
        """从JSON数据中解析视频信息"""
        # 查找视频URL和相关信息
        def find_video_url(obj, path=""):
            """递归查找视频URL"""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    # 常见的视频相关键
                    if key.lower() in ['video', 'src', 'url', 'source', 'file'] and isinstance(value, str):
                        if any(ext in value.lower() for ext in ['.mp4', '.webm', '.m3u8']):
                            return value, current_path
                    
                    # 查找视频对象
                    if key.lower() in ['video', 'videos', 'media', 'sources'] and isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                video_url = item.get('url') or item.get('src') or item.get('file')
                                if video_url:
                                    return video_url, current_path
                    
                    # 递归查找
                    result = find_video_url(value, current_path)
                    if result:
                        return result
                        
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    result = find_video_url(item, f"{path}[{i}]")
                    if result:
                        return result
            
            return None, None
        
        video_url, path = find_video_url(data)
        if video_url:
            full_url = urljoin(page_url, video_url)
            
            # 尝试从JSON数据中提取分辨率信息
            resolution = "未知"
            title = "未知标题"
            
            # 查找分辨率信息
            def find_resolution(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        
                        if key.lower() in ['resolution', 'quality', 'size', 'dimension'] and isinstance(value, str):
                            if any(p in value.lower() for p in ['1080p', '720p', '480p', '360p']):
                                return value
                        
                        # 递归查找
                        result = find_resolution(value, current_path)
                        if result:
                            return result
                return None
            
            resolution = find_resolution(data) or "未知"
            
            # 查找标题信息
            def find_title(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        
                        if key.lower() in ['title', 'name', 'description'] and isinstance(value, str):
                            return value[:100]  # 限制长度
                        
                        # 递归查找
                        result = find_title(value, current_path)
                        if result:
                            return result
                return None
            
            title = find_title(data) or "未知标题"
            
            return VideoInfo(
                url=full_url,
                title=title,
                resolution=resolution,
                file_size=0
            )
        
        return None
    
    def _parse_video_from_tag(self, video_content: str, page_url: str) -> Optional[VideoInfo]:
        """从video标签内容中解析视频信息"""
        # 提取src属性
        src_match = re.search(r'src=["\']([^"\']+)["\']', video_content)
        if src_match:
            video_url = urljoin(page_url, src_match.group(1))
            return VideoInfo(
                url=video_url,
                title="未知标题",
                resolution="未知",
                file_size=0
            )
        return None
    
    def _parse_video_from_source(self, source_tag: str, page_url: str) -> Optional[VideoInfo]:
        """从source标签中解析视频信息"""
        # 提取src属性
        src_match = re.search(r'src=["\']([^"\']+)["\']', source_tag)
        if src_match:
            video_url = urljoin(page_url, src_match.group(1))
            
            # 尝试提取分辨率信息
            resolution = "未知"
            
            # 从quality属性获取
            quality_match = re.search(r'quality=["\']([^"\']+)["\']', source_tag, re.IGNORECASE)
            if quality_match:
                resolution = quality_match.group(1)
            
            # 从其他属性获取分辨率信息
            if 'data-quality' in source_tag.lower():
                data_quality_match = re.search(r'data-quality=["\']([^"\']+)["\']', source_tag, re.IGNORECASE)
                if data_quality_match:
                    resolution = data_quality_match.group(1)
            
            # 从URL参数获取质量信息
            if '?' in video_url:
                url_params = urlparse(video_url).query
                if 'quality' in url_params:
                    quality_from_url = urlparse(video_url).query.split('quality=')[1].split('&')[0]
                    resolution = quality_from_url
            
            # 从文件名推断分辨率
            if '1080p' in video_url.lower() or '1920x1080' in video_url.lower():
                resolution = "1080p"
            elif '720p' in video_url.lower() or '1280x720' in video_url.lower():
                resolution = "720p"
            elif '480p' in video_url.lower() or '854x480' in video_url.lower():
                resolution = "480p"
            elif '360p' in video_url.lower() or '640x360' in video_url.lower():
                resolution = "360p"
            
            return VideoInfo(
                url=video_url,
                title="未知标题",
                resolution=resolution,
                file_size=0
            )
        return None
    
    async def _get_video_file_size(self, video_url: str) -> int:
        """获取视频文件大小"""
        if not self.session:
            await self.create_session()
        
        try:
            async with self.session.head(video_url, allow_redirects=True) as response:
                if response.status == 200:
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        return int(content_length)
        except Exception as e:
            print(f"获取视频文件大小失败: {e}")
        
        return 0
    
    def _is_ad_video(self, video_info: VideoInfo) -> bool:
        """判断是否为广告视频"""
        # 从配置中获取广告过滤设置
        ad_size_threshold = getattr(self.config, 'ad_video_size_threshold', 10 * 1024 * 1024)  # 默认10MB
        ad_filter_enabled = getattr(self.config, 'enable_ad_filter', True)  # 默认启用
        
        if not ad_filter_enabled:
            return False
        
        # 基于文件大小判断
        if video_info.file_size < ad_size_threshold:
            print(f"基于文件大小判断为广告视频: {video_info.file_size / 1024 / 1024:.2f}MB < {ad_size_threshold / 1024 / 1024:.1f}MB")
            return True
        
        # 基于URL模式判断
        ad_indicators = ['ad', 'advertisement', 'promo', 'sponsored', 'banner', 'commercial']
        url_lower = video_info.url.lower()
        
        for indicator in ad_indicators:
            if indicator in url_lower:
                print(f"基于URL模式判断为广告视频: 包含 '{indicator}'")
                return True
        
        # 基于标题判断（如果有的话）
        if video_info.title:
            title_lower = video_info.title.lower()
            for indicator in ad_indicators:
                if indicator in title_lower:
                    print(f"基于标题判断为广告视频: 包含 '{indicator}'")
                    return True
        
        return False
    
    async def get_best_quality_video(self, url: str) -> Optional[VideoInfo]:
        """获取最高质量的视频（过滤广告视频）"""
        video_info = await self.get_video_info(url)
        
        if not video_info:
            return None
        
        # 如果是广告视频，不下载
        if video_info.is_ad_video:
            print("检测到广告视频，跳过下载")
            return None
        
        print(f"视频质量: {video_info.resolution}")
        return video_info
    
    def compare_video_quality(self, video1: VideoInfo, video2: VideoInfo) -> VideoInfo:
        """比较两个视频的质量，返回质量更高的视频"""
        quality_order = {
            '8k': 8,
            '4k': 7,
            '2160p': 7,
            '1440p': 6,
            '1080p': 5,
            '720p': 4,
            '480p': 3,
            '360p': 2,
            '240p': 1,
            '未知': 0
        }
        
        # 获取质量分数
        score1 = quality_order.get(video1.resolution.lower(), 0)
        score2 = quality_order.get(video2.resolution.lower(), 0)
        
        # 如果质量相同，比较文件大小（更大的文件通常质量更好）
        if score1 == score2:
            if video1.file_size > video2.file_size:
                return video1
            else:
                return video2
        
        # 返回质量分数更高的视频
        return video1 if score1 > score2 else video2
    
    async def get_multiple_videos_and_select_best(self, url: str) -> Optional[VideoInfo]:
        """获取多个视频链接并选择最佳质量的视频"""
        html = await self.fetch_page(url)
        if not html:
            return None
        
        # 检查是否是Cloudflare挑战页面
        if 'Just a moment...' in html or 'cf-chl-bypass' in html:
            print("检测到Cloudflare挑战页面，需要手动处理")
            return None
        
        videos = []
        
        # 1. 从JSON数据中获取多个视频
        json_pattern = r'<script[^>]*type=["\']application/json["\'][^>]*>([^<]+)</script>'
        json_matches = re.findall(json_pattern, html, re.IGNORECASE | re.DOTALL)
        
        for json_str in json_matches:
            try:
                data = json.loads(json_str)
                video_info = self._parse_video_from_json(data, url)
                if video_info:
                    videos.append(video_info)
            except json.JSONDecodeError:
                continue
        
        # 2. 从video标签中获取视频
        video_pattern = r'<video[^>]*>(.*?)</video>'
        video_matches = re.findall(video_pattern, html, re.IGNORECASE | re.DOTALL)
        
        for video_content in video_matches:
            video_info = self._parse_video_from_tag(video_content, url)
            if video_info:
                videos.append(video_info)
        
        # 3. 从source标签中获取视频
        source_pattern = r'<source[^>]*>'
        source_matches = re.findall(source_pattern, html, re.IGNORECASE)
        
        for source_tag in source_matches:
            video_info = self._parse_video_from_source(source_tag, url)
            if video_info:
                videos.append(video_info)
        
        if not videos:
            print("未找到任何视频")
            return None
        
        # 去重（基于URL）
        unique_videos = []
        seen_urls = set()
        
        for video in videos:
            if video.url not in seen_urls:
                seen_urls.add(video.url)
                unique_videos.append(video)
        
        print(f"找到 {len(unique_videos)} 个不同的视频")
        
        # 获取每个视频的文件大小并过滤广告视频
        valid_videos = []
        for video in unique_videos:
            video.file_size = await self._get_video_file_size(video.url)
            video.is_ad_video = self._is_ad_video(video)
            
            if not video.is_ad_video:
                valid_videos.append(video)
                print(f"视频: {video.url}")
                print(f"分辨率: {video.resolution}")
                print(f"文件大小: {video.file_size / 1024 / 1024:.2f} MB")
                print("---")
            else:
                print(f"跳过广告视频: {video.url}")
        
        if not valid_videos:
            print("没有找到有效的视频（可能都是广告视频）")
            return None
        
        # 选择最佳质量的视频
        best_video = valid_videos[0]
        for video in valid_videos[1:]:
            best_video = self.compare_video_quality(best_video, video)
        
        print(f"选择最佳视频: {best_video.url}")
        print(f"最佳分辨率: {best_video.resolution}")
        print(f"文件大小: {best_video.file_size / 1024 / 1024:.2f} MB")
        
        return best_video
    
    async def parse_page(self, url: str) -> List[str]:
        """解析页面，提取媒体链接（兼容性方法）"""
        html = await self.fetch_page(url)
        if not html:
            return []
        
        # 检查是否是Cloudflare挑战页面
        if 'Just a moment...' in html or 'cf-chl-bypass' in html:
            print("检测到Cloudflare挑战页面，需要手动处理")
            return []
        
        # 提取图片链接 (常见格式)
        image_patterns = [
            r'src=["\']([^"\']+\.(?:jpg|jpeg|png|gif|webp|bmp))["\']',
            r'data-src=["\']([^"\']+\.(?:jpg|jpeg|png|gif|webp|bmp))["\']',
            r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>',
        ]
        
        # 提取视频链接
        video_patterns = [
            r'src=["\']([^"\']+\.(?:mp4|webm|avi|mov|mkv|flv))["\']',
            r'<video[^>]+src=["\']([^"\']+)["\'][^>]*>',
            r'<source[^>]+src=["\']([^"\']+)["\'][^>]*>',
        ]
        
        media_urls = []
        
        # 搜索图片
        for pattern in image_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                full_url = urljoin(url, match)
                if full_url not in media_urls:
                    media_urls.append(full_url)
        
        # 搜索视频
        for pattern in video_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                full_url = urljoin(url, match)
                if full_url not in media_urls:
                    media_urls.append(full_url)
        
        # 去重并返回
        return list(set(media_urls))
    
    async def test_connection(self) -> bool:
        """测试连接"""
        test_url = "https://ask4porn.cc"
        html = await self.fetch_page(test_url)
        return html is not None and 'Just a moment...' not in html