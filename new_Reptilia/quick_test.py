#!/usr/bin/env python3
"""
快速测试脚本 - 诊断爬虫问题
"""
import asyncio
import aiohttp
import os
import json


async def test_network():
    """测试基本网络连接"""
    print("=" * 60)
    print("1️⃣  测试基本网络连接")
    print("=" * 60)
    
    test_urls = [
        ("https://www.google.com", "Google"),
        ("https://www.baidu.com", "百度"),
        ("https://ask4porn.cc", "目标网站"),
    ]
    
    async with aiohttp.ClientSession() as session:
        for url, name in test_urls:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    status = resp.status
                    if status == 200:
                        print(f"  ✅ {name}: 连接成功 (状态码: {status})")
                    elif status == 403:
                        print(f"  ⚠️  {name}: 被拒绝访问 (状态码: {status}) - 可能需要Cookie")
                    else:
                        print(f"  ⚠️  {name}: 状态码 {status}")
            except asyncio.TimeoutError:
                print(f"  ❌ {name}: 连接超时")
            except Exception as e:
                print(f"  ❌ {name}: {type(e).__name__} - {str(e)[:50]}")
    print()


async def test_cookie_file():
    """测试Cookie文件"""
    print("=" * 60)
    print("2️⃣  检查Cookie文件")
    print("=" * 60)
    
    cookie_files = ["raw_cookies.json", "cURL.txt", "cURL_new.txt"]
    
    for file in cookie_files:
        if os.path.exists(file):
            print(f"  ✅ {file}: 存在")
            
            if file.endswith('.json'):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        cookies = json.load(f)
                    
                    cf_clearance = None
                    for c in cookies:
                        if c.get('name') == 'cf_clearance':
                            cf_clearance = c.get('value', '')[:30] + '...'
                            break
                    
                    if cf_clearance:
                        print(f"     └─ cf_clearance: {cf_clearance}")
                    else:
                        print(f"     └─ ⚠️  缺少 cf_clearance")
                except Exception as e:
                    print(f"     └─ ❌ 解析失败: {e}")
        else:
            print(f"  ❌ {file}: 不存在")
    print()


async def test_with_cookie():
    """使用Cookie测试访问"""
    print("=" * 60)
    print("3️⃣  使用Cookie测试访问目标网站")
    print("=" * 60)
    
    cookie_file = "raw_cookies.json"
    if not os.path.exists(cookie_file):
        print("  ⚠️  Cookie文件不存在，跳过此测试")
        print("  💡 提示: 运行 python get_cf_cookie.py 获取Cookie")
        return
    
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        # 构建Cookie字符串
        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Cookie': cookie_string,
        }
        
        url = "https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                status = resp.status
                text = await resp.text()
                
                if status == 200:
                    if 'Just a moment' in text or 'cf-chl' in text:
                        print(f"  ⚠️  状态码200，但遇到Cloudflare验证页面")
                        print("  💡 Cookie可能已过期，请重新获取")
                    else:
                        print(f"  ✅ 访问成功! 状态码: {status}")
                        print(f"     页面长度: {len(text)} 字符")
                        
                        # 检查是否有视频内容
                        if 'video' in text.lower() or '.mp4' in text.lower():
                            print(f"     └─ ✅ 页面包含视频相关内容")
                        else:
                            print(f"     └─ ⚠️  未检测到视频内容")
                elif status == 403:
                    print(f"  ❌ 访问被拒绝 (403)")
                    print("  💡 Cookie无效或已过期")
                else:
                    print(f"  ⚠️  状态码: {status}")
                    
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
    print()


async def test_playwright():
    """测试Playwright是否可用"""
    print("=" * 60)
    print("4️⃣  测试Playwright环境")
    print("=" * 60)
    
    try:
        from playwright.async_api import async_playwright
        print("  ✅ Playwright 已安装")
        
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
                print("  ✅ Chromium 浏览器可用")
                await browser.close()
            except Exception as e:
                print(f"  ❌ Chromium 启动失败: {e}")
                print("  💡 运行: playwright install chromium")
    except ImportError:
        print("  ❌ Playwright 未安装")
        print("  💡 运行: pip install playwright && playwright install chromium")
    print()


def print_summary():
    """打印总结和建议"""
    print("=" * 60)
    print("📋 问题诊断总结")
    print("=" * 60)
    print("""
如果测试失败，请按以下步骤操作:

1. 网络问题:
   - 检查是否需要VPN/代理访问目标网站
   - 确认防火墙没有阻止连接

2. Cookie问题:
   - 运行: python get_cf_cookie.py
   - 在弹出的浏览器中完成Cloudflare验证
   - 等待Cookie保存到 raw_cookies.json

3. Playwright问题:
   - 安装: pip install playwright
   - 安装浏览器: playwright install chromium

4. 使用爬虫:
   - 获取Cookie后运行: python main.py
   - 选择选项3 (Playwright视频提取器)
""")


async def main():
    """主函数"""
    print("\n" + "🔍 Ask4Porn 爬虫诊断工具".center(60) + "\n")
    
    await test_network()
    await test_cookie_file()
    await test_with_cookie()
    await test_playwright()
    print_summary()


if __name__ == "__main__":
    asyncio.run(main())
