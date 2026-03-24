"""
智能下载器 - 综合多种方法绕过Cloudflare保护
"""

import asyncio
import aiohttp
import json
import re
import os
from pathlib import Path
import time
from playwright.async_api import async_playwright

class SmartDownloader:
    def __init__(self, target_url):
        self.target_url = target_url
        self.session = None
        self.cookies_loaded = False
        
    async def method_1_try_existing_cookies(self):
        """方法1: 尝试使用现有的Cookie"""
        print("🔧 方法1: 尝试现有Cookie...")
        
        try:
            # 加载现有Cookie
            cookie_files = ['raw_cookies.json', 'advanced_cookies.json', 'homepage_cookies.json']
            cookies = None
            
            for cookie_file in cookie_files:
                if os.path.exists(cookie_file):
                    try:
                        with open(cookie_file, 'r') as f:
                            cookie_data = json.load(f)
                            if isinstance(cookie_data, list) and cookie_data:
                                cookies = cookie_data
                                print(f"✅ 加载Cookie文件: {cookie_file}")
                                break
                    except:
                        continue
            
            if not cookies:
                print("❌ 未找到有效的Cookie文件")
                return False
                
            # 创建会话
            connector = aiohttp.TCPConnector(limit=10)
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
            
            # 准备Cookie
            cookie_jar = {}
            for cookie in cookies:
                if 'name' in cookie and 'value' in cookie:
                    cookie_jar[cookie['name']] = cookie['value']
            
            # 尝试访问
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            async with self.session.get(self.target_url, headers=headers, cookies=cookie_jar) as response:
                if response.status == 200:
                    print("✅ Cookie方法成功!")
                    content = await response.text()
                    await self.save_and_parse_content(content, "method1_cookies")
                    return True
                else:
                    print(f"❌ Cookie方法失败，状态码: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Cookie方法出错: {e}")
            return False
        finally:
            if self.session:
                await self.session.close()
    
    async def method_2_browser_automation(self):
        """方法2: 使用浏览器自动化"""
        print("🔧 方法2: 浏览器自动化...")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                
                # 设置用户代理
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                
                # 访问页面
                print("🌐 访问目标页面...")
                await page.goto(self.target_url, timeout=60000)
                
                # 等待页面加载
                print("⏳ 等待页面加载...")
                await asyncio.sleep(30)
                
                # 检查是否需要验证
                title = await page.title()
                print(f"📄 页面标题: {title}")
                
                if "请稍候" in title or "just a moment" in title.lower():
                    print("⏳ 检测到Cloudflare验证，等待...")
                    # 等待用户手动完成验证
                    input("请在浏览器中完成Cloudflare验证，然后按回车继续...")
                
                # 获取页面内容
                content = await page.content()
                print("✅ 成功获取页面内容")
                
                await self.save_and_parse_content(content, "method2_browser")
                
                # 尝试提取视频链接
                video_links = await self.extract_videos_from_page(page)
                if video_links:
                    await self.download_videos(video_links)
                
                await browser.close()
                return True
                
        except Exception as e:
            print(f"❌ 浏览器自动化出错: {e}")
            return False
    
    async def method_3_playwright_api(self):
        """方法3: 使用Playwright API直接访问"""
        print("🔧 方法3: Playwright API...")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                # 尝试访问
                response = await page.goto(self.target_url, timeout=60000)
                
                if response.status == 200:
                    content = await page.content()
                    print("✅ Playwright API成功!")
                    await self.save_and_parse_content(content, "method3_playwright")
                    
                    # 提取视频
                    video_links = await self.extract_videos_from_page(page)
                    if video_links:
                        await self.download_videos(video_links)
                    
                    await browser.close()
                    return True
                else:
                    print(f"❌ Playwright API失败，状态码: {response.status}")
                    await browser.close()
                    return False
                    
        except Exception as e:
            print(f"❌ Playwright API出错: {e}")
            return False
    
    async def method_4_proxy_request(self):
        """方法4: 使用代理请求"""
        print("🔧 方法4: 代理请求...")
        
        try:
            # 使用公共代理服务
            proxies = [
                'https://api.allorigins.win/raw?url=',
                'https://cors-anywhere.herokuapp.com/',
                'https://thingproxy.freeboard.io/fetch/'
            ]
            
            for proxy in proxies:
                try:
                    proxy_url = proxy + self.target_url
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(proxy_url, timeout=30) as response:
                            if response.status == 200:
                                content = await response.text()
                                print(f"✅ 代理 {proxy} 成功!")
                                await self.save_and_parse_content(content, "method4_proxy")
                                return True
                            else:
                                print(f"❌ 代理 {proxy} 失败，状态码: {response.status}")
                except:
                    continue
                    
            return False
            
        except Exception as e:
            print(f"❌ 代理请求出错: {e}")
            return False
    
    async def extract_videos_from_page(self, page):
        """从页面提取视频链接"""
        print("🔍 提取视频链接...")
        
        try:
            # 等待视频元素加载
            await page.wait_for_selector('video, source', timeout=30000)
            
            # 获取所有视频元素
            video_elements = await page.query_selector_all('video, source')
            
            video_links = []
            for video_element in video_elements:
                src = await video_element.get_attribute('src')
                if src and src.startswith('http'):
                    video_links.append(src)
                    print(f"🎬 找到视频: {src}")
            
            # 查找data-src属性
            data_src_elements = await page.query_selector_all('[data-src]')
            for element in data_src_elements:
                src = await element.get_attribute('data-src')
                if src and '.mp4' in src:
                    video_links.append(src)
                    print(f"🎬 找到data-src视频: {src}")
            
            # 查找JavaScript中的视频URL
            js_content = await page.content()
            video_urls = re.findall(r'["\']([^"\']*\.mp4[^"\']*)["\']', js_content)
            video_links.extend(video_urls)
            
            # 去重
            video_links = list(set(video_links))
            
            print(f"✅ 总共找到 {len(video_links)} 个视频链接")
            return video_links
            
        except Exception as e:
            print(f"❌ 视频提取出错: {e}")
            return []
    
    async def save_and_parse_content(self, content, method_name):
        """保存并解析内容"""
        filename = f"{method_name}_content.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 内容已保存到: {filename}")
        
        # 解析内容
        await self.parse_html_content(content, method_name)
    
    async def parse_html_content(self, content, source):
        """解析HTML内容"""
        print(f"🔍 解析 {source} 内容...")
        
        # 查找视频标签
        video_patterns = [
            r'<video[^>]*src=["\']([^"\']+)["\']',
            r'<source[^>]*src=["\']([^"\']+)["\']',
            r'data-src=["\']([^"\']*\.mp4[^"\']*)["\']'
        ]
        
        videos_found = []
        for pattern in video_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            videos_found.extend(matches)
        
        if videos_found:
            print(f"📹 在 {source} 中找到 {len(videos_found)} 个视频")
            await self.download_videos(videos_found, source)
        else:
            print(f"❌ 在 {source} 中未找到视频")
    
    async def download_videos(self, video_links, source="direct"):
        """下载视频"""
        print(f"📥 开始下载 {len(video_links)} 个视频...")
        
        if not video_links:
            return
        
        os.makedirs('downloads', exist_ok=True)
        
        for i, video_url in enumerate(video_links, 1):
            try:
                filename = f"downloads/video_{source}_{i}.mp4"
                print(f"📹 下载视频 {i}/{len(video_links)}: {video_url}")
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(video_url, timeout=60) as response:
                        if response.status == 200:
                            with open(filename, 'wb') as f:
                                async for chunk in response.content.iter_chunked(8192):
                                    f.write(chunk)
                            print(f"✅ 视频已保存: {filename}")
                        else:
                            print(f"❌ 视频下载失败，状态码: {response.status}")
                            
            except Exception as e:
                print(f"❌ 视频下载出错: {e}")
    
    async def manual_solution(self):
        """手动解决方案"""
        print("🔧 方法5: 手动解决方案...")
        print("""
        由于自动化方法都失败了，请尝试以下手动步骤：
        
        1. 在浏览器中访问: https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/
        2. 手动完成Cloudflare验证
        3. 等待页面完全加载
        4. 右键页面 -> 查看页面源代码
        5. 搜索 '.mp4' 查找视频链接
        6. 或者在开发者工具的Network面板中查找视频请求
        
        如果找到了视频链接，请运行:
        python manual_download.py <视频链接1> <视频链接2> ...
        """)
        
        # 创建手动下载脚本
        manual_script = '''#!/usr/bin/env python3
import aiohttp
import asyncio
import sys

async def download_video(url, filename):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                with open(filename, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                print(f"✅ 下载完成: {filename}")
            else:
                print(f"❌ 下载失败: {url}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python manual_download.py <视频链接1> <视频链接2> ...")
        sys.exit(1)
    
    urls = sys.argv[1:]
    for i, url in enumerate(urls, 1):
        filename = f"manual_video_{i}.mp4"
        asyncio.run(download_video(url, filename))
'''
        
        with open('manual_download.py', 'w') as f:
            f.write(manual_script)
        
        print("✅ 已创建 manual_download.py 脚本")
    
    async def run_all_methods(self):
        """运行所有方法"""
        print("🚀 开始智能下载流程...")
        print(f"🎯 目标URL: {self.target_url}")
        print("=" * 60)
        
        methods = [
            self.method_1_try_existing_cookies,
            self.method_2_browser_automation,
            self.method_3_playwright_api,
            self.method_4_proxy_request
        ]
        
        for method in methods:
            try:
                if await method():
                    print("✅ 下载成功!")
                    return True
            except Exception as e:
                print(f"❌ 方法执行出错: {e}")
            
            print("-" * 40)
        
        # 如果所有自动方法都失败，提供手动解决方案
        await self.manual_solution()
        return False

async def main():
    target_url = "https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/"
    
    downloader = SmartDownloader(target_url)
    success = await downloader.run_all_methods()
    
    if success:
        print("🎉 下载完成!")
    else:
        print("💡 请查看手动解决方案")

if __name__ == "__main__":
    asyncio.run(main())