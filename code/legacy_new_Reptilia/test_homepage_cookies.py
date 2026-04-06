#!/usr/bin/env python3
"""
主页Cookie获取测试
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def test_homepage_cookies():
    """测试主页Cookie获取"""
    print("测试主页Cookie获取...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            print("访问主页...")
            await page.goto("https://ask4porn.cc", timeout=30000)
            
            print("等待验证...")
            await asyncio.sleep(30)  # 等待30秒
            
            # 检查页面状态
            title = await page.title()
            print(f"页面标题: {title}")
            
            # 获取Cookie
            cookies = await browser.cookies()
            print(f"获取到 {len(cookies)} 个Cookie")
            
            for cookie in cookies:
                print(f"  {cookie['name']}: {cookie['value'][:30]}...")
            
            # 查找Cloudflare相关Cookie
            cf_cookies = [c for c in cookies if 'cf' in c['name'].lower()]
            print(f"\n找到 {len(cf_cookies)} 个Cloudflare Cookie")
            
            if cf_cookies:
                # 保存格式化的Cookie
                formatted = []
                for c in cf_cookies:
                    formatted.append({
                        'name': c['name'],
                        'value': c['value'],
                        'url': 'https://ask4porn.cc'
                    })
                
                with open('homepage_cookies.json', 'w') as f:
                    json.dump(formatted, f, indent=2)
                print("主页Cookie已保存")
            
        except Exception as e:
            print(f"错误: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_homepage_cookies())