#!/usr/bin/env python3
"""
高级Cloudflare Cookie获取工具
专门用于获取有效的cf_clearance cookie
"""
import asyncio
import json
import time
from datetime import datetime
from playwright.async_api import async_playwright

async def advanced_cookie_extractor():
    """高级Cookie提取器"""
    print("🔧 高级Cloudflare Cookie获取工具")
    print("=" * 50)
    
    target_url = "https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/"
    
    async with async_playwright() as p:
        # 启动浏览器（显示浏览器以便手动验证）
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        # 创建上下文
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            java_script_enabled=True
        )
        
        page = await context.new_page()
        
        try:
            print("🌐 开始访问网站...")
            await page.goto(target_url, wait_until='domcontentloaded', timeout=60000)
            
            # 检查页面状态
            print("⏳ 等待Cloudflare验证...")
            
            # 等待更长时间，最多5分钟
            max_wait = 300  # 5分钟
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                # 检查页面内容
                content = await page.content()
                title = await page.title()
                
                print(f"⏰ 当前时间: {int(time.time() - start_time)}秒")
                print(f"📄 页面标题: {title}")
                
                # 检查是否已通过验证
                if '403' not in title and 'Access denied' not in content and 'Just a moment' not in content:
                    print("✅ 验证通过！")
                    break
                
                # 检查当前URL
                current_url = page.url
                print(f"🔗 当前URL: {current_url}")
                
                # 等待10秒后再次检查
                await asyncio.sleep(10)
            
            print("\n🍪 获取所有Cookie...")
            
            # 获取所有Cookie
            all_cookies = await context.cookies()
            
            # 打印所有Cookie用于调试
            print(f"找到 {len(all_cookies)} 个Cookie:")
            for cookie in all_cookies:
                print(f"  {cookie['name']}: {cookie['value'][:50]}...")
            
            # 保存Cookie到文件
            formatted_cookies = []
            for cookie in all_cookies:
                # 为Playwright格式化
                formatted_cookie = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'url': 'https://ask4porn.cc',  # 使用基础URL
                    'path': cookie.get('path', '/'),
                }
                formatted_cookies.append(formatted_cookie)
            
            # 保存到文件
            with open('advanced_cookies.json', 'w', encoding='utf-8') as f:
                json.dump(formatted_cookies, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Cookie已保存到 advanced_cookies.json")
            
            # 检查是否获取到关键Cookie
            cookie_names = [c['name'] for c in all_cookies]
            if 'cf_clearance' in cookie_names:
                cf_clearance = next(c['value'] for c in all_cookies if c['name'] == 'cf_clearance')
                print(f"🎉 成功获取cf_clearance: {cf_clearance}")
                
                # 保存单独的cf_clearance
                with open('cf_clearance_only.json', 'w') as f:
                    json.dump([{'name': 'cf_clearance', 'value': cf_clearance, 'url': 'https://ask4porn.cc'}], f)
                print("💾 cf_clearance已保存到 cf_clearance_only.json")
            else:
                print("⚠️ 未获取到cf_clearance")
            
            return all_cookies
            
        except Exception as e:
            print(f"❌ 错误: {e}")
            return []
        finally:
            input("按回车键关闭浏览器...")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(advanced_cookie_extractor())