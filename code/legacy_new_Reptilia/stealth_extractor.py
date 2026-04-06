#!/usr/bin/env python3
"""
隐蔽视频提取器 - 模拟真实用户行为
"""
import asyncio
import re
import random
from playwright.async_api import async_playwright


async def human_like_delay():
    """模拟人类操作延迟"""
    await asyncio.sleep(random.uniform(1.5, 3.5))


async def extract_video(url: str):
    """提取视频，模拟真实用户"""
    print(f"🎯 目标: {url}\n")
    
    async with async_playwright() as p:
        # 使用更真实的浏览器配置
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-automation',
                '--no-sandbox',
            ]
        )
        
        # 创建更真实的浏览器上下文
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
        )
        
        # 注入脚本隐藏自动化特征
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = {runtime: {}};
        """)
        
        page = await context.new_page()
        
        # 捕获的视频URL
        video_urls = []
        iframe_urls = []
        
        # 监听网络请求
        async def on_response(response):
            url = response.url
            content_type = response.headers.get('content-type', '')
            
            if '.mp4' in url or '.m3u8' in url or 'video' in content_type:
                if url not in video_urls:
                    video_urls.append(url)
                    print(f"📹 捕获: {url[:80]}...")
        
        page.on('response', on_response)
        
        print("🌐 访问页面...")
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        
        # 模拟人类等待
        print("⏳ 等待页面加载...")
        await human_like_delay()
        await human_like_delay()
        
        # 模拟鼠标移动
        print("🖱️ 模拟用户行为...")
        await page.mouse.move(random.randint(100, 500), random.randint(100, 300))
        await human_like_delay()
        
        # 滚动页面
        await page.evaluate('window.scrollBy(0, 300)')
        await human_like_delay()
        
        # 查找iframe
        print("\n🔍 查找视频iframe...")
        iframes = await page.query_selector_all('iframe')
        
        for iframe in iframes:
            src = await iframe.get_attribute('src')
            if src and 'embed' in src and 'ad' not in src.lower():
                iframe_urls.append(src)
                print(f"  找到: {src}")
        
        # 如果找到embed iframe，访问它获取真实视频
        if iframe_urls:
            embed_url = iframe_urls[0]
            if not embed_url.startswith('http'):
                embed_url = 'https:' + embed_url
            
            print(f"\n🎬 访问嵌入页面: {embed_url}")
            
            # 新标签页访问embed
            embed_page = await context.new_page()
            embed_page.on('response', on_response)
            
            try:
                await embed_page.goto(embed_url, wait_until='domcontentloaded', timeout=30000)
                await human_like_delay()
                await human_like_delay()
                
                # 尝试点击播放
                try:
                    play_btn = await embed_page.query_selector('.vjs-big-play-button, .play-button, video')
                    if play_btn:
                        await play_btn.click()
                        print("  ▶️ 点击播放")
                        await human_like_delay()
                except:
                    pass
                
                # 从embed页面提取视频
                embed_content = await embed_page.content()
                
                # 查找视频源
                patterns = [
                    r'file:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                    r'src:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                    r'source:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                    r'["\']([^"\']+\.mp4[^"\']*)["\']',
                    r'["\']([^"\']+\.m3u8[^"\']*)["\']',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, embed_content, re.IGNORECASE)
                    for m in matches:
                        if m not in video_urls and 'http' in m:
                            video_urls.append(m)
                            print(f"  📹 从embed找到: {m[:60]}...")
                
                await embed_page.close()
                
            except Exception as e:
                print(f"  ⚠️ embed访问失败: {e}")
        
        # 结果
        print(f"\n{'='*50}")
        print(f"📊 结果: 找到 {len(video_urls)} 个视频URL")
        
        if video_urls:
            print("\n🎬 视频列表:")
            for i, v in enumerate(video_urls, 1):
                print(f"  {i}. {v}")
            
            # 保存结果
            with open('video_urls.txt', 'w') as f:
                for v in video_urls:
                    f.write(v + '\n')
            print("\n💾 已保存到 video_urls.txt")
        else:
            print("\n⚠️ 未找到视频")
            print("💡 可能原因:")
            print("   1. 网站检测到自动化")
            print("   2. 视频需要登录")
            print("   3. 视频通过加密方式加载")
        
        print("\n浏览器保持打开，你可以手动检查...")
        input("按回车关闭...")
        await browser.close()
        
        return video_urls


if __name__ == "__main__":
    url = "https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/"
    asyncio.run(extract_video(url))
