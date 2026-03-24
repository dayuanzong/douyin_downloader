#!/usr/bin/env python3
"""
测试不同的Cookie格式
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def test_cookie_formats():
    """测试不同Cookie格式"""
    print("🧪 测试不同Cookie格式...")
    
    # 测试1: 只有url
    print("\n1. 测试只有url格式:")
    cookie1 = [{"name": "test", "value": "value1", "url": "https://ask4porn.cc"}]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        try:
            await context.add_cookies(cookie1)
            print("✅ 成功: 只有url")
        except Exception as e:
            print(f"❌ 失败: {e}")
        
        await browser.close()
    
    # 测试2: 只有path
    print("\n2. 测试只有path格式:")
    cookie2 = [{"name": "test", "value": "value2", "path": "/"}]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        try:
            await context.add_cookies(cookie2)
            print("✅ 成功: 只有path")
        except Exception as e:
            print(f"❌ 失败: {e}")
        
        await browser.close()
    
    # 测试3: url + path
    print("\n3. 测试url + path格式:")
    cookie3 = [{"name": "test", "value": "value3", "url": "https://ask4porn.cc", "path": "/"}]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        try:
            await context.add_cookies(cookie3)
            print("✅ 成功: url + path")
        except Exception as e:
            print(f"❌ 失败: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_cookie_formats())