"""
基于浏览器代理的解决方案
由于Cookie方式无法绕过Cloudflare保护，我们使用浏览器代理来直接访问内容
"""

import asyncio
import json
import aiohttp
import subprocess
import os
from playwright.async_api import async_playwright

class BrowserProxyDownloader:
    def __init__(self, target_url):
        self.target_url = target_url
        self.session = None
        self.browser = None
        
    async def setup_browser_proxy(self):
        """设置浏览器代理"""
        print("🚀 设置浏览器代理...")
        
        # 启动Selenium Standalone Chrome
        print("📡 启动Chrome代理服务器...")
        self.chrome_process = subprocess.Popen([
            "python", "-m", "selenium.webdriver.remote.remote_connection", 
            "--port=4444"
        ])
        
        # 启动浏览器代理
        print("🌐 启动浏览器代理...")
        proxy_script = f'''
        const chrome = require('chrome-aws-lambda');
        const { Builder, By, until } = require('selenium-webdriver');
        
        (async function main() {{
            let driver = await new Builder()
                .forBrowser('chrome')
                .build();
            
            console.log("✅ 浏览器代理已启动");
            
            // 访问目标网站
            await driver.get('{self.target_url}');
            console.log("✅ 已访问目标网站");
            
            // 等待页面加载完成
            await driver.wait(until.titleIsNot(''), 30000);
            console.log("✅ 页面加载完成");
            
            // 获取页面内容
            let pageSource = await driver.getPageSource();
            console.log("✅ 已获取页面内容");
            
            // 保存页面内容
            require('fs').writeFileSync('proxy_page_content.html', pageSource);
            console.log("✅ 页面内容已保存到 proxy_page_content.html");
            
            // 提取视频链接
            let videoLinks = await driver.findElements(By.tagName('video'));
            console.log(`✅ 找到 {{videoLinks.length}} 个视频元素`);
            
            for (let i = 0; i < videoLinks.length; i++) {{
                let src = await videoLinks[i].getAttribute('src');
                if (src) {{
                    console.log(`📹 视频链接 ${{i+1}}: ${{src}}`);
                }}
            }}
            
            await driver.quit();
            process.exit(0);
        }})();
        '''
        
        with open('proxy_browser.js', 'w') as f:
            f.write(proxy_script)
        
        # 运行代理脚本
        self.proxy_process = subprocess.Popen(['node', 'proxy_browser.js'])
        
    async def download_videos_with_proxy(self):
        """使用代理下载视频"""
        print("🎯 开始代理下载...")
        
        # 创建HTTP会话
        self.session = aiohttp.ClientSession()
        
        try:
            # 等待代理浏览器启动
            await asyncio.sleep(10)
            
            # 尝试访问目标页面
            async with self.session.get(self.target_url) as response:
                if response.status == 200:
                    content = await response.text()
                    print("✅ 通过代理成功访问页面")
                    
                    # 保存页面内容
                    with open('proxy_content.html', 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    # 解析视频链接
                    video_links = self.extract_video_links(content)
                    print(f"🎬 找到 {len(video_links)} 个视频链接")
                    
                    if video_links:
                        await self.download_videos(video_links)
                    else:
                        print("❌ 未找到视频链接")
                else:
                    print(f"❌ 代理访问失败，状态码: {response.status}")
                    
        except Exception as e:
            print(f"❌ 代理下载出错: {e}")
            
    def extract_video_links(self, html_content):
        """从HTML内容中提取视频链接"""
        import re
        
        # 查找video标签的src属性
        video_patterns = [
            r'<video[^>]*src=["\']([^"\']+)["\']',
            r'<source[^>]*src=["\']([^"\']+)["\']',
            r'data-src=["\']([^"\']*\.mp4[^"\']*)["\']',
            r'["\']([^"\']*\.mp4[^"\']*)["\']'
        ]
        
        video_links = []
        for pattern in video_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            video_links.extend(matches)
        
        # 去重
        video_links = list(set(video_links))
        
        return [link for link in video_links if link.startswith('http')]
        
    async def download_videos(self, video_links):
        """下载视频"""
        print(f"📥 开始下载 {len(video_links)} 个视频...")
        
        for i, video_url in enumerate(video_links, 1):
            print(f"📹 下载视频 {i}/{len(video_links)}: {video_url}")
            
            try:
                async with self.session.get(video_url) as response:
                    if response.status == 200:
                        # 保存视频
                        filename = f"video_{i}.mp4"
                        with open(filename, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        print(f"✅ 视频已保存: {filename}")
                    else:
                        print(f"❌ 视频下载失败，状态码: {response.status}")
            except Exception as e:
                print(f"❌ 视频下载出错: {e}")
                
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
            
        if hasattr(self, 'chrome_process'):
            self.chrome_process.terminate()
            
        if hasattr(self, 'proxy_process'):
            self.proxy_process.terminate()

async def main():
    target_url = "https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/"
    
    downloader = BrowserProxyDownloader(target_url)
    
    try:
        await downloader.setup_browser_proxy()
        await downloader.download_videos_with_proxy()
    finally:
        await downloader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())