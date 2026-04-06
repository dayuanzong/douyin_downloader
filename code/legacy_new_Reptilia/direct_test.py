#!/usr/bin/env python3
"""直接测试视频提取"""
import asyncio
import re
from playwright.async_api import async_playwright


async def test_extract():
    url = "https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/"
    # 注意：这个URL可能是视频详情页，需要确认
    
    print("🚀 启动浏览器...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        page = await context.new_page()
        
        # 捕获网络请求中的视频
        video_urls = []
        
        async def handle_response(response):
            url = response.url
            content_type = response.headers.get('content-type', '')
            if '.mp4' in url or '.m3u8' in url or 'video' in content_type:
                video_urls.append(url)
                print(f"📹 捕获视频: {url[:80]}...")
        
        page.on('response', handle_response)
        
        print(f"🌐 访问: {url}")
        try:
            await page.goto(url, wait_until='load', timeout=60000)
        except Exception as e:
            print(f"⚠️ 页面加载: {e}")
        
        # 等待页面稳定
        print("⏳ 等待页面稳定...")
        await page.wait_for_timeout(8000)
        
        # 等待页面不再导航
        try:
            await page.wait_for_load_state('networkidle', timeout=20000)
        except:
            print("  网络未完全空闲，继续...")
        
        # 滚动页面以触发懒加载
        print("📜 滚动页面...")
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
        await page.wait_for_timeout(3000)
        
        # 检查页面内容
        try:
            content = await page.content()
        except Exception as e:
            print(f"⚠️ 获取内容失败: {e}")
            await page.wait_for_timeout(5000)
            content = await page.content()
        
        # 检查页面标题
        title = await page.title()
        print(f"📄 页面标题: {title}")
        
        if 'Just a moment' in content:
            print("⚠️ 遇到 Cloudflare，等待验证...")
            await page.wait_for_timeout(15000)
            content = await page.content()
        
        # 从HTML中提取视频
        print("\n🔍 从HTML提取视频链接...")
        
        # 查找所有视频相关的URL
        patterns = [
            r'https?://[^"\s<>]+\.mp4[^"\s<>]*',
            r'https?://[^"\s<>]+\.m3u8[^"\s<>]*',
            r'src=["\']([^"\']+\.mp4[^"\']*)["\']',
            r'file:\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for m in matches:
                if m not in video_urls:
                    video_urls.append(m)
                    print(f"  找到: {m[:80]}...")
        
        # 尝试点击播放按钮
        print("\n🖱️ 尝试点击播放...")
        try:
            video_elem = await page.query_selector('video')
            if video_elem:
                await video_elem.click()
                await page.wait_for_timeout(3000)
        except:
            pass
        
        # 执行JS获取视频源
        print("\n🔧 执行JS提取...")
        try:
            js_videos = await page.evaluate('''() => {
                const videos = [];
                document.querySelectorAll('video').forEach(v => {
                    if (v.src) videos.push(v.src);
                    if (v.currentSrc) videos.push(v.currentSrc);
                });
                document.querySelectorAll('source').forEach(s => {
                    if (s.src) videos.push(s.src);
                });
                return videos;
            }''')
            for v in js_videos:
                if v and v not in video_urls:
                    video_urls.append(v)
                    print(f"  JS找到: {v[:80]}...")
        except Exception as e:
            print(f"  JS错误: {e}")
        
        print(f"\n📊 总共找到 {len(video_urls)} 个视频URL")
        
        if video_urls:
            print("\n🎬 视频列表:")
            for i, v in enumerate(video_urls, 1):
                print(f"  {i}. {v}")
        else:
            print("\n❌ 未找到视频URL")
            
            # 检查是否有iframe
            iframes = await page.query_selector_all('iframe')
            print(f"\n🔍 找到 {len(iframes)} 个iframe")
            for i, iframe in enumerate(iframes):
                src = await iframe.get_attribute('src')
                print(f"  iframe {i+1}: {src}")
            
            # 检查是否有video-player区域
            player = await page.query_selector('.video-player-area, .responsive-player, #player')
            if player:
                print("\n✅ 找到视频播放器区域")
                player_html = await player.inner_html()
                print(f"  播放器HTML长度: {len(player_html)}")
            else:
                print("\n⚠️ 未找到视频播放器区域")
            
            # 保存页面
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(content)
            print("\n💾 已保存到 debug_page.html")
        
        print("\n🔍 浏览器保持打开，请手动检查页面...")
        print("   查看是否有视频播放器，以及视频是如何加载的")
        input("\n按回车关闭浏览器...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_extract())
