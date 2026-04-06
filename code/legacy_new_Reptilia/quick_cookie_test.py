#!/usr/bin/env python3
"""
快速测试Cookie加载和网站访问
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def quick_test():
    """快速测试"""
    print("🧪 快速测试Cookie和网站访问...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 加载Cookie
        try:
            with open('raw_cookies.json', 'r') as f:
                cookies = json.load(f)
            print(f"📁 原始Cookie: {cookies}")
            
            # 格式化Cookie为Playwright格式
            formatted_cookies = []
            for cookie in cookies:
                if 'name' in cookie and 'value' in cookie:
                    formatted_cookie = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'url': cookie.get('url', 'https://ask4porn.cc'),
                        'path': cookie.get('path', '/'),
                    }
                    formatted_cookies.append(formatted_cookie)
            
            print(f"📁 格式化后Cookie: {formatted_cookies}")
            
            # 添加到浏览器
            await context.add_cookies(formatted_cookies)
            print("✅ Cookie加载成功")
            
        except Exception as e:
            print(f"❌ Cookie加载失败: {e}")
        
        # 测试网站访问
        try:
            print("🌐 测试网站访问...")
            response = await page.goto("https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/", timeout=30000)
            print(f"状态码: {response.status}")
            
            if response.status == 200:
                print("✅ 网站访问成功!")
                # 获取页面标题
                title = await page.title()
                print(f"页面标题: {title}")
            else:
                print(f"❌ 网站访问失败，状态码: {response.status}")
                
        except Exception as e:
            print(f"❌ 网站访问失败: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(quick_test())