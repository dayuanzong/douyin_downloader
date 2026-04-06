#!/usr/bin/env python3
"""
视频提取器 - 使用Playwright模拟浏览器，绕过Cloudflare，提取真实视频链接
"""
import asyncio
import json
import re
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

from playwright.async_api import async_playwright, Page, Response


@dataclass
class VideoInfo:
    """视频信息"""
    url: str
    title: str = ""
    resolution: str = "未知"
    file_size: int = 0
    is_ad_video: bool = False
    width: int = 0
    height: int = 0
    duration: float = 0.0
    mime_type: str = ""


class VideoExtractor:
    """视频提取器"""
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        """初始化"""
        self.headless = headless
        self.timeout = timeout
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        
        # 视频URL模式
        self.video_patterns = [
            r'https?://[^"\s]+?\.(?:mp4|webm|avi|mov|mkv|flv|m3u8)(?:[?#].*?)?',
            r'blob:https?://[^"\s]+',
        ]
        
        # 视频MIME类型
        self.video_mime_types = [
            'video/mp4',
            'video/webm',
            'video/ogg',
            'video/x-matroska',
            'video/quicktime',
            'video/x-msvideo',
            'application/x-mpegURL',
            'application/vnd.apple.mpegurl',
        ]
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def start(self):
        """启动Playwright浏览器"""
        self.playwright = await async_playwright().start()
        
        # 使用Chromium浏览器（支持更广）
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
            ]
        )
        
        # 创建上下文，设置User-Agent和视口
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            java_script_enabled=True,
            bypass_csp=True,
        )
        
        # 拦截网络请求，捕获视频URL
        await self.context.route('**/*', self._route_handler)
        
        # 创建页面
        self.page = await self.context.new_page()
        
        # 存储捕获的视频请求
        self.video_requests = []
    
    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def _route_handler(self, route, request):
        """路由处理器，用于捕获视频请求"""
        # 检查请求是否为视频
        resource_type = request.resource_type
        url = request.url
        
        # 如果是视频资源，记录信息
        if resource_type == 'media' or any(mime in (request.headers.get('content-type', '') or '').lower() for mime in self.video_mime_types):
            video_info = {
                'url': url,
                'method': request.method,
                'headers': request.headers,
                'resource_type': resource_type,
                'frame': request.frame.name if request.frame else 'main',
            }
            self.video_requests.append(video_info)
            
            # 打印调试信息
            print(f"捕获到视频请求: {url[:100]}...")
        
        # 继续请求
        await route.continue_()
    
    async def load_cookies(self, cookie_file: str = "raw_cookies.json"):
        """加载Cookie文件"""
        import os
        
        if not os.path.exists(cookie_file):
            print(f"⚠️  Cookie文件不存在: {cookie_file}")
            return False
        
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies_data = json.load(f)
            
            # 检查是否有 cf_clearance
            has_cf_clearance = any(c.get('name') == 'cf_clearance' for c in cookies_data)
            if not has_cf_clearance:
                print("⚠️  Cookie缺少 cf_clearance，可能无法绕过Cloudflare")
                print("💡 提示: 运行 python get_cf_cookie.py 获取有效Cookie")
            
            cookies = []
            for cookie in cookies_data:
                # Playwright 要求 sameSite 必须是 "Strict", "Lax", "None" 之一
                same_site = cookie.get('sameSite', 'Lax')
                if same_site not in ['Strict', 'Lax', 'None']:
                    same_site = 'Lax'
                
                # 构建简化的Cookie格式
                formatted_cookie = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'url': "https://ask4porn.cc",
                    'path': cookie.get('path', '/'),
                    'sameSite': same_site,
                }
                
                # 处理 expires
                expires = cookie.get('expires', -1)
                if expires and expires > 0:
                    formatted_cookie['expires'] = expires
                
                cookies.append(formatted_cookie)
            
            # 加载到浏览器上下文
            await self.context.add_cookies(cookies)
            print(f"✅ 已加载 {len(cookies)} 个Cookie")
            return True
            
        except Exception as e:
            print(f"❌ Cookie加载失败: {e}")
            return False
    
    async def extract_videos_from_page(self, url: str, wait_time: int = 10000) -> List[VideoInfo]:
        """从页面提取视频"""
        print(f"正在访问页面: {url}")
        
        # 清空之前捕获的视频请求
        self.video_requests = []
        
        try:
            # 导航到页面
            response = await self.page.goto(url, wait_until='networkidle', timeout=self.timeout)
            
            if response and response.status >= 400:
                print(f"页面访问失败，状态码: {response.status}")
                return []
            
            # 等待页面加载
            print("等待页面加载...")
            await self.page.wait_for_timeout(wait_time)
            
            # 尝试点击可能的播放按钮
            await self._try_click_play_button()
            
            # 等待视频加载
            await self.page.wait_for_timeout(3000)
            
            # 从多个来源提取视频
            videos = []
            
            # 1. 从捕获的网络请求中提取
            network_videos = await self._extract_videos_from_network()
            videos.extend(network_videos)
            
            # 2. 从页面HTML中提取
            html_videos = await self._extract_videos_from_html()
            videos.extend(html_videos)
            
            # 3. 从JavaScript变量中提取
            js_videos = await self._extract_videos_from_javascript()
            videos.extend(js_videos)
            
            # 4. 从video元素中提取
            element_videos = await self._extract_videos_from_elements()
            videos.extend(element_videos)
            
            # 去重并返回
            return self._deduplicate_videos(videos)
            
        except Exception as e:
            print(f"提取视频时发生错误: {e}")
            return []
    
    async def _try_click_play_button(self):
        """尝试点击播放按钮"""
        play_selectors = [
            'button:has-text("播放")',
            'button:has-text("Play")',
            '.play-button',
            '.video-play',
            '[aria-label="播放"]',
            '[aria-label="Play"]',
            'video',
        ]
        
        for selector in play_selectors:
            try:
                if await self.page.is_visible(selector):
                    await self.page.click(selector)
                    print(f"已点击播放按钮: {selector}")
                    await self.page.wait_for_timeout(2000)
                    break
            except:
                continue
    
    async def _extract_videos_from_network(self) -> List[VideoInfo]:
        """从网络请求中提取视频"""
        videos = []
        
        for request in self.video_requests:
            url = request['url']
            
            # 跳过广告和跟踪URL
            if self._is_ad_url(url):
                continue
            
            video_info = VideoInfo(
                url=url,
                title=f"网络视频 {len(videos) + 1}",
            )
            
            # 尝试从URL推断分辨率
            video_info.resolution = self._infer_resolution_from_url(url)
            
            # 尝试从headers获取信息
            headers = request.get('headers', {})
            content_type = headers.get('content-type', '')
            if content_type:
                video_info.mime_type = content_type.split(';')[0]
            
            videos.append(video_info)
            
            print(f"从网络请求找到视频: {url[:80]}...")
        
        return videos
    
    async def _extract_videos_from_html(self) -> List[VideoInfo]:
        """从HTML中提取视频"""
        videos = []
        
        # 获取页面HTML
        html = await self.page.content()
        
        # 使用正则表达式查找视频URL
        for pattern in self.video_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                # 转换为绝对URL
                if match.startswith('blob:'):
                    # 处理blob URL
                    continue
                else:
                    url = urljoin(self.page.url, match)
                
                # 跳过广告和跟踪URL
                if self._is_ad_url(url):
                    continue
                
                video_info = VideoInfo(
                    url=url,
                    title=f"HTML视频 {len(videos) + 1}",
                )
                
                # 尝试从URL推断分辨率
                video_info.resolution = self._infer_resolution_from_url(url)
                
                videos.append(video_info)
                
                print(f"从HTML找到视频: {url[:80]}...")
        
        return videos
    
    async def _extract_videos_from_javascript(self) -> List[VideoInfo]:
        """从JavaScript变量中提取视频"""
        videos = []
        
        # 尝试从常见的JavaScript变量中提取视频URL
        js_scripts = [
            # 尝试获取window.videoUrl等变量
            """
            (function() {
                const videoSources = [];
                
                // 查找常见变量名
                const videoVars = ['videoUrl', 'videoURL', 'videoSrc', 'videoSRC', 'videoSource', 'videoData'];
                for (const varName of videoVars) {
                    if (window[varName]) {
                        videoSources.push(window[varName]);
                    }
                }
                
                // 查找video元素的数据属性
                document.querySelectorAll('video').forEach(video => {
                    if (video.src) videoSources.push(video.src);
                    if (video.currentSrc) videoSources.push(video.currentSrc);
                });
                
                return videoSources;
            })();
            """,
            
            # 尝试获取JSON-LD数据
            """
            (function() {
                const videoSources = [];
                const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
                
                jsonLdScripts.forEach(script => {
                    try {
                        const data = JSON.parse(script.textContent);
                        
                        function findVideoUrls(obj) {
                            if (typeof obj === 'string' && obj.match(/\.(mp4|webm|avi|mov|mkv|flv)/i)) {
                                videoSources.push(obj);
                            } else if (Array.isArray(obj)) {
                                obj.forEach(item => findVideoUrls(item));
                            } else if (typeof obj === 'object' && obj !== null) {
                                Object.values(obj).forEach(value => findVideoUrls(value));
                            }
                        }
                        
                        findVideoUrls(data);
                    } catch (e) {
                        // 忽略解析错误
                    }
                });
                
                return videoSources;
            })();
            """,
        ]
        
        for script in js_scripts:
            try:
                result = await self.page.evaluate(script)
                if result and isinstance(result, list):
                    for url in result:
                        if url and isinstance(url, str):
                            # 转换为绝对URL
                            full_url = urljoin(self.page.url, url)
                            
                            # 跳过广告和跟踪URL
                            if self._is_ad_url(full_url):
                                continue
                            
                            video_info = VideoInfo(
                                url=full_url,
                                title=f"JS视频 {len(videos) + 1}",
                            )
                            
                            # 尝试从URL推断分辨率
                            video_info.resolution = self._infer_resolution_from_url(full_url)
                            
                            videos.append(video_info)
                            
                            print(f"从JavaScript找到视频: {full_url[:80]}...")
            except Exception as e:
                # 忽略JavaScript执行错误
                continue
        
        return videos
    
    async def _extract_videos_from_elements(self) -> List[VideoInfo]:
        """从页面元素中提取视频"""
        videos = []
        
        # 查找video元素
        video_elements = await self.page.query_selector_all('video')
        
        for i, video_element in enumerate(video_elements):
            try:
                # 获取video属性
                src = await video_element.get_attribute('src')
                current_src = await video_element.get_attribute('currentSrc')
                poster = await video_element.get_attribute('poster')
                
                # 收集所有可能的视频源
                video_sources = []
                if src:
                    video_sources.append(src)
                if current_src:
                    video_sources.append(current_src)
                
                # 从source子元素中提取
                source_elements = await video_element.query_selector_all('source')
                for source in source_elements:
                    source_src = await source.get_attribute('src')
                    if source_src:
                        video_sources.append(source_src)
                
                for video_url in video_sources:
                    if video_url:
                        # 转换为绝对URL
                        full_url = urljoin(self.page.url, video_url)
                        
                        # 跳过广告和跟踪URL
                        if self._is_ad_url(full_url):
                            continue
                        
                        # 获取视频元素属性
                        width = await video_element.get_attribute('width') or 0
                        height = await video_element.get_attribute('height') or 0
                        duration = await video_element.get_attribute('duration') or 0
                        
                        try:
                            width = int(width) if width else 0
                            height = int(height) if height else 0
                            duration = float(duration) if duration else 0.0
                        except (ValueError, TypeError):
                            width = height = 0
                            duration = 0.0
                        
                        video_info = VideoInfo(
                            url=full_url,
                            title=f"元素视频 {len(videos) + 1}",
                            width=width,
                            height=height,
                            duration=duration,
                        )
                        
                        # 尝试从URL推断分辨率
                        video_info.resolution = self._infer_resolution_from_url(full_url)
                        
                        videos.append(video_info)
                        
                        print(f"从video元素找到视频: {full_url[:80]}...")
            except Exception as e:
                # 忽略元素提取错误
                continue
        
        return videos
    
    def _deduplicate_videos(self, videos: List[VideoInfo]) -> List[VideoInfo]:
        """去重视频列表"""
        seen_urls = set()
        unique_videos = []
        
        for video in videos:
            # 使用URL作为去重依据
            if video.url not in seen_urls:
                seen_urls.add(video.url)
                unique_videos.append(video)
        
        return unique_videos
    
    def _is_ad_url(self, url: str) -> bool:
        """判断是否为广告或跟踪URL"""
        ad_keywords = [
            'ads', 'advertisement', 'banner', 'tracking', 'analytics',
            'google-analytics', 'doubleclick', 'facebook.com/tr',
            'googletagmanager', 'pixel', 'beacon', 'adsystem',
            'adserving', 'adserver', 'tracking', 'analytics'
        ]
        
        url_lower = url.lower()
        return any(keyword in url_lower for keyword in ad_keywords)
    
    def _infer_resolution_from_url(self, url: str) -> str:
        """从URL推断视频分辨率"""
        # 常见的分辨率模式
        resolution_patterns = [
            (r'(\d{3,4})x(\d{3,4})', lambda m: f"{m.group(1)}x{m.group(2)}"),
            (r'_(\d{3,4})p', lambda m: f"{m.group(1)}p"),
            (r'_(\d{3,4})x(\d{3,4})_', lambda m: f"{m.group(1)}x{m.group(2)}"),
            (r'-(\d{3,4})p', lambda m: f"{m.group(1)}p"),
            (r'(\d{3,4})p', lambda m: f"{m.group(1)}p"),
        ]
        
        for pattern, formatter in resolution_patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                try:
                    return formatter(match)
                except:
                    continue
        
        return "未知"
    
    async def test_connection(self) -> bool:
        """测试网络连接到目标网站"""
        print("🔗 正在测试网络连接...")
        
        try:
            # 首先检查是否已启动浏览器
            if not self.browser:
                await self.start()
            
            # 自动加载Cookie
            print("🍪 正在加载Cookie...")
            await self.load_cookies()
            
            # 测试访问基础URL
            test_url = "https://ask4porn.cc"
            print(f"🌐 访问测试URL: {test_url}")
            
            response = await self.page.goto(test_url, wait_until='networkidle', timeout=30000)
            
            if response and response.status == 200:
                print("✅ 网络连接正常")
                return True
            else:
                print(f"⚠️  访问响应状态: {response.status if response else 'None'}")
                return False
                
        except Exception as e:
            print(f"❌ 网络连接测试失败: {str(e)}")
            return False