#!/usr/bin/env python3
"""
网站访问状态检查工具
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def check_website_status():
    """检查网站访问状态"""
    print("🔍 网站访问状态检查")
    print("=" * 40)
    
    target_url = "https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        # 测试1: 不使用Cookie直接访问
        print("\n1️⃣ 测试: 无Cookie访问")
        try:
            response = await page.goto(target_url, timeout=30000)
            print(f"状态码: {response.status}")
            if response.status == 200:
                print("✅ 无Cookie访问成功")
                title = await page.title()
                print(f"页面标题: {title}")
            else:
                print("❌ 无Cookie访问失败")
        except Exception as e:
            print(f"❌ 访问错误: {e}")
        
        # 测试2: 使用当前Cookie访问
        print("\n2️⃣ 测试: 使用当前Cookie")
        try:
            # 尝试加载Cookie
            try:
                with open('raw_cookies.json', 'r') as f:
                    cookies = json.load(f)
                print(f"加载Cookie: {len(cookies)}个")
                await context.add_cookies(cookies)
                print("✅ Cookie加载成功")
            except Exception as e:
                print(f"❌ Cookie加载失败: {e}")
            
            # 重新访问
            response = await page.goto(target_url, timeout=30000)
            print(f"状态码: {response.status}")
            if response.status == 200:
                print("✅ 使用Cookie访问成功")
                title = await page.title()
                print(f"页面标题: {title}")
            else:
                print("❌ 使用Cookie访问失败")
                
        except Exception as e:
            print(f"❌ 访问错误: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_website_status())