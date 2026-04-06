#!/usr/bin/env python3
"""
Cookie状态总结和解决方案
"""
import json
import os

def analyze_cookie_status():
    """分析Cookie状态"""
    print("📊 Cookie状态分析报告")
    print("=" * 50)
    
    # 检查Cookie文件
    cookie_files = ['raw_cookies.json', 'cURL_new.txt', 'advanced_cookies.json']
    
    for file_name in cookie_files:
        if os.path.exists(file_name):
            print(f"\n📁 找到文件: {file_name}")
            try:
                if file_name.endswith('.json'):
                    with open(file_name, 'r') as f:
                        data = json.load(f)
                    print(f"   内容: {len(data) if isinstance(data, list) else 1} 个Cookie")
                    if isinstance(data, list) and data:
                        for cookie in data:
                            print(f"   - {cookie.get('name', 'Unknown')}: {cookie.get('value', 'No value')[:30]}...")
                else:
                    with open(file_name, 'r') as f:
                        content = f.read()
                    print(f"   内容长度: {len(content)} 字符")
                    if 'cf_clearance' in content:
                        print("   ✅ 包含cf_clearance")
                    else:
                        print("   ❌ 未包含cf_clearance")
            except Exception as e:
                print(f"   ❌ 读取失败: {e}")
        else:
            print(f"\n❌ 文件不存在: {file_name}")
    
    # 分析问题
    print(f"\n🔍 问题分析:")
    print("1. 当前只有 cf_chl_rc_ni Cookie")
    print("2. 缺少关键的 cf_clearance Cookie")
    print("3. 网站返回403状态码，访问被拒绝")
    
    # 提供解决方案
    print(f"\n💡 解决方案:")
    print("1. 运行 python advanced_cookie_extractor.py 手动获取cf_clearance")
    print("2. 等待更长时间让Cloudflare完成验证")
    print("3. 尝试访问主页面获取完整Cookie")
    
    # 创建简单的测试脚本
    print(f"\n🧪 创建测试脚本...")
    
    test_script = '''#!/usr/bin/env python3
"""
简单测试脚本
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def simple_test():
    print("🧪 简单测试...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # 访问主页获取Cookie
        print("🌐 访问主页...")
        await page.goto("https://ask4porn.cc", timeout=30000)
        
        print("⏳ 等待验证...")
        await asyncio.sleep(30)  # 等待30秒
        
        # 获取Cookie
        cookies = await browser.cookies()
        print(f"🍪 获取到 {len(cookies)} 个Cookie")
        
        for cookie in cookies:
            if 'cf' in cookie['name']:
                print(f"Cloudflare Cookie: {cookie['name']} = {cookie['value'][:50]}...")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(simple_test())
'''
    
    with open('simple_cookie_test.py', 'w') as f:
        f.write(test_script)
    
    print("✅ 已创建 simple_cookie_test.py")

if __name__ == "__main__":
    analyze_cookie_status()