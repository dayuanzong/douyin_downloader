#!/usr/bin/env python3
"""
Cloudflare Cookie 获取工具
使用 Playwright 自动获取 cf_clearance cookie
"""
import asyncio
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright


async def get_cloudflare_cookies(url: str = "https://ask4porn.cc/", 
                                  headless: bool = False,
                                  wait_time: int = 30):
    """
    使用 Playwright 获取 Cloudflare cookies
    
    Args:
        url: 目标网站URL
        headless: 是否无头模式（建议False，方便手动验证）
        wait_time: 等待验证的时间（秒）
    """
    print(f"🚀 启动浏览器...")
    print(f"📍 目标URL: {url}")
    print(f"⏱️  等待时间: {wait_time}秒")
    print("-" * 50)
    
    async with async_playwright() as p:
        # 启动浏览器（非无头模式，方便手动验证）
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ]
        )
        
        # 创建上下文
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        )
        
        page = await context.new_page()
        
        try:
            print("🌐 正在访问网站...")
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            # 检查是否遇到 Cloudflare 挑战
            content = await page.content()
            if 'Just a moment' in content or 'cf-chl' in content:
                print("⚠️  检测到 Cloudflare 验证页面")
                print(f"👆 请在浏览器中完成验证（等待 {wait_time} 秒）...")
                
                # 等待用户完成验证
                for i in range(wait_time, 0, -1):
                    print(f"   剩余时间: {i}秒", end='\r')
                    await asyncio.sleep(1)
                    
                    # 检查是否已通过验证
                    content = await page.content()
                    if 'Just a moment' not in content and 'cf-chl' not in content:
                        print("\n✅ 验证已通过!")
                        break
                print()
            else:
                print("✅ 直接访问成功，无需验证")
            
            # 获取所有 cookies
            cookies = await context.cookies()
            
            # 筛选 Cloudflare 相关的 cookies
            cf_cookies = {}
            all_cookies = []
            
            for cookie in cookies:
                all_cookies.append({
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie['domain'],
                    'path': cookie.get('path', '/'),
                    'expires': cookie.get('expires', -1),
                    'httpOnly': cookie.get('httpOnly', False),
                    'secure': cookie.get('secure', False),
                    'sameSite': cookie.get('sameSite', 'Lax'),
                })
                
                if 'cf' in cookie['name'].lower() or cookie['name'] in ['__cf_bm']:
                    cf_cookies[cookie['name']] = cookie['value']
            
            # 保存所有 cookies 到文件
            with open('raw_cookies.json', 'w', encoding='utf-8') as f:
                json.dump(all_cookies, f, indent=2, ensure_ascii=False)
            print(f"💾 已保存所有 cookies 到 raw_cookies.json")
            
            # 显示 Cloudflare cookies
            print("\n" + "=" * 50)
            print("🍪 Cloudflare Cookies:")
            print("=" * 50)
            
            if cf_cookies:
                for name, value in cf_cookies.items():
                    print(f"  {name}: {value[:50]}..." if len(value) > 50 else f"  {name}: {value}")
                
                # 检查是否有 cf_clearance
                if 'cf_clearance' in cf_cookies:
                    print("\n✅ 成功获取 cf_clearance!")
                    print(f"   值: {cf_cookies['cf_clearance'][:50]}...")
                else:
                    print("\n⚠️  未获取到 cf_clearance，可能需要更长的等待时间或手动验证")
            else:
                print("  未找到 Cloudflare cookies")
            
            # 生成 cURL 命令
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in all_cookies])
            curl_command = f'''curl "{url}" \\
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \\
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \\
  -b "{cookie_string}"'''
            
            with open('cURL_new.txt', 'w', encoding='utf-8') as f:
                f.write(curl_command)
            print(f"\n💾 已保存 cURL 命令到 cURL_new.txt")
            
            return cf_cookies, all_cookies
            
        except Exception as e:
            print(f"❌ 发生错误: {e}")
            return {}, []
        finally:
            await browser.close()
            print("\n🔒 浏览器已关闭")


async def main():
    """主函数"""
    print("=" * 60)
    print("       Cloudflare Cookie 获取工具")
    print("=" * 60)
    print()
    
    # 获取用户输入
    url = input("请输入目标URL (直接回车使用默认): ").strip()
    if not url:
        url = "https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/"
    
    wait_time = input("请输入等待时间(秒，默认30): ").strip()
    wait_time = int(wait_time) if wait_time.isdigit() else 30
    
    headless_input = input("是否使用无头模式? (y/n，默认n): ").strip().lower()
    headless = headless_input == 'y'
    
    print()
    cf_cookies, all_cookies = await get_cloudflare_cookies(url, headless, wait_time)
    
    print("\n" + "=" * 60)
    print("完成! 请将 raw_cookies.json 用于爬虫程序")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
