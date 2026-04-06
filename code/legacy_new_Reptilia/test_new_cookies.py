#!/usr/bin/env python3
"""
测试新的Cookie文件
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def test_new_cookies():
    """测试新的Cookie"""
    print("🧪 测试新的Cookie...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 测试1: 使用新的Cookie
        try:
            with open('advanced_cookies.json', 'r') as f:
                cookies = json.load(f)
            print(f"📁 加载新Cookie: {cookies}")
            
            await context.add_cookies(cookies)
            print("✅ 新Cookie加载成功")
            
            # 访问网站
            response = await page.goto("https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/", timeout=30000)
            print(f"🌐 网站访问状态码: {response.status}")
            
            if response.status == 200:
                print("✅ 网站访问成功!")
                title = await page.title()
                print(f"📄 页面标题: {title}")
            else:
                print(f"❌ 网站访问失败，状态码: {response.status}")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_new_cookies())