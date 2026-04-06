#!/usr/bin/env python3
"""
完整的Cookie获取和网站访问测试
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def complete_cookie_test():
    """完整的Cookie测试"""
    print("🚀 完整Cookie获取和测试...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # 步骤1: 访问主页
            print("📍 步骤1: 访问主页...")
            await page.goto("https://ask4porn.cc", timeout=30000)
            print("⏳ 等待Cloudflare验证...")
            await asyncio.sleep(45)  # 等待45秒
            
            # 检查页面状态
            title = await page.title()
            print(f"📄 主页标题: {title}")
            
            # 获取主页Cookie
            context = await browser.new_context()
            homepage_cookies = await context.cookies()
            print(f"🍪 主页Cookie数量: {len(homepage_cookies)}")
            
            # 筛选Cloudflare相关Cookie
            cf_cookies = [c for c in homepage_cookies if 'cf' in c['name'].lower() or '_cf' in c['name'].lower()]
            print(f"🌪️ Cloudflare相关Cookie: {len(cf_cookies)}")
            for c in cf_cookies:
                print(f"  {c['name']}: {c['value'][:50]}...")
            
            # 步骤2: 访问具体页面
            print("\n📍 步骤2: 访问具体页面...")
            await page.goto("https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/", timeout=30000)
            print("⏳ 等待页面加载...")
            await asyncio.sleep(20)  # 等待20秒
            
            # 检查页面状态
            final_title = await page.title()
            print(f"📄 最终页面标题: {final_title}")
            
            # 获取最终Cookie
            final_cookies = await context.cookies()
            print(f"🍪 最终Cookie数量: {len(final_cookies)}")
            
            # 检查是否有cf_clearance
            has_cf_clearance = any('cf_clearance' in c['name'] for c in final_cookies)
            print(f"🎯 包含cf_clearance: {'是' if has_cf_clearance else '否'}")
            
            if has_cf_clearance:
                print("🎉 成功获取cf_clearance!")
                cf_clearance = next(c for c in final_cookies if 'cf_clearance' in c['name'])
                print(f"🔑 cf_clearance值: {cf_clearance['value']}")
                
                # 保存最终Cookie
                formatted_cookies = []
                for c in final_cookies:
                    formatted_cookies.append({
                        'name': c['name'],
                        'value': c['value'],
                        'url': 'https://ask4porn.cc'
                    })
                
                with open('final_cookies.json', 'w') as f:
                    json.dump(formatted_cookies, f, indent=2)
                print("💾 最终Cookie已保存到 final_cookies.json")
            
            # 测试网站访问
            print("\n🧪 测试网站访问...")
            response = await page.goto("https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/", timeout=30000)
            print(f"🌐 状态码: {response.status}")
            
            if response.status == 200:
                print("✅ 网站访问成功!")
                # 获取页面内容长度
                content = await page.content()
                print(f"📊 页面内容长度: {len(content)} 字符")
            else:
                print(f"❌ 网站访问失败，状态码: {response.status}")
            
        except Exception as e:
            print(f"❌ 发生错误: {e}")
        finally:
            input("按回车键关闭浏览器...")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(complete_cookie_test())