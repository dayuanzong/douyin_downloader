#!/usr/bin/env python3
"""
测试修复后的Cookie
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def test_fixed_cookie():
    """测试修复后的Cookie"""
    print("🧪 测试修复后的Cookie...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 加载Cookie
        try:
            with open('raw_cookies.json', 'r') as f:
                cookies = json.load(f)
            print(f"📁 加载Cookie: {cookies}")
            
            await context.add_cookies(cookies)
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
                title = await page.title()
                print(f"页面标题: {title}")
            else:
                print(f"❌ 网站访问失败，状态码: {response.status}")
                
        except Exception as e:
            print(f"❌ 网站访问失败: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_fixed_cookie())