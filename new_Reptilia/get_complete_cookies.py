#!/usr/bin/env python3
"""
简单Cookie获取工具
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def get_complete_cookies():
    """获取完整Cookie"""
    print("开始获取完整Cookie...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("访问主页...")
        await page.goto("https://ask4porn.cc", timeout=30000)
        
        print("等待Cloudflare验证...")
        print("请在打开的浏览器中完成验证，然后按回车键继续...")
        input()
        
        # 获取所有Cookie
        cookies = await browser.cookies()
        print(f"获取到 {len(cookies)} 个Cookie:")
        
        cf_cookies = []
        for cookie in cookies:
            if 'cf' in cookie['name'].lower():
                print(f"Cloudflare Cookie: {cookie['name']} = {cookie['value'][:50]}...")
                cf_cookies.append(cookie)
        
        # 保存到文件
        if cf_cookies:
            # 格式化为Playwright格式
            formatted_cookies = []
            for cookie in cf_cookies:
                formatted_cookies.append({
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'url': 'https://ask4porn.cc'
                })
            
            with open('complete_cookies.json', 'w') as f:
                json.dump(formatted_cookies, f, indent=2)
            print("Cookie已保存到 complete_cookies.json")
        else:
            print("未找到Cloudflare Cookie")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_complete_cookies())