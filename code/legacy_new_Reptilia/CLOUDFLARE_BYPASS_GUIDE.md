# Cloudflare 绕过指南

## 问题分析

目标网站 `https://ask4porn.cc/` 使用了 Cloudflare 防护，导致我们的爬虫程序收到 403 Forbidden 错误。Cloudflare 会检测以下特征：

1. **JavaScript 挑战** - 需要执行 JavaScript 代码来验证
2. **Cookie 验证** - 需要有效的 `cf_clearance` cookie
3. **浏览器指纹** - 检测 User-Agent、HTTP 头等
4. **行为分析** - 检测请求频率、模式等

## 手动绕过方案

### 方法一：手动获取 Cookie

1. **使用浏览器访问网站**
   - 打开 Chrome/Firefox 浏览器
   - 访问 `https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/`
   - 完成 Cloudflare 验证（可能需要点击验证框）

2. **获取 Cookie**
   - 按 F12 打开开发者工具
   - 切换到 "Application" 或 "存储" 标签
   - 找到 Cookies → `https://ask4porn.cc`
   - 复制 `cf_clearance` 的值

3. **配置爬虫**
   - 打开 `config.py` 文件
   - 找到 `cloudflare_cookies` 配置项
   - 添加获取到的 cookie：
     ```python
     cloudflare_cookies = {
         'cf_clearance': '你的_cf_clearance_值'
     }
     ```

### 方法二：使用 Playwright/Selenium 自动化

1. **安装 Playwright**
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **创建自动化脚本**
   ```python
   # cloudflare_bypass.py
   import asyncio
   from playwright.async_api import async_playwright
   
   async def get_cloudflare_cookies():
       async with async_playwright() as p:
           browser = await p.chromium.launch(headless=False)
           context = await browser.new_context()
           page = await context.new_page()
           
           # 访问目标网站
           await page.goto('https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/')
           
           # 等待 Cloudflare 验证完成
           await page.wait_for_timeout(10000)  # 等待10秒
           
           # 获取 cookies
           cookies = await context.cookies()
           cf_cookies = {}
           for cookie in cookies:
               if 'cf_' in cookie['name']:
                   cf_cookies[cookie['name']] = cookie['value']
           
           await browser.close()
           return cf_cookies
   
   if __name__ == '__main__':
       cookies = asyncio.run(get_cloudflare_cookies())
       print('获取到的 Cloudflare cookies:')
       for name, value in cookies.items():
           print(f'{name}: {value}')
   ```

### 方法三：使用第三方服务

1. **ScrapingBee API** - 提供 Cloudflare 绕过服务
2. **ScraperAPI** - 处理反爬虫机制
3. **ZenRows** - 专门的反爬虫解决方案

## 代码优化建议

### 1. 更新 User-Agent

在 `config.py` 中使用更真实的浏览器 User-Agent：

```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}
```

### 2. 添加请求延迟

避免被检测为机器人：

```python
import random
import asyncio

async def safe_request(self, url):
    # 随机延迟 1-3 秒
    await asyncio.sleep(random.uniform(1, 3))
    # 发送请求
    return await self.session.get(url, headers=self.headers)
```

### 3. 使用代理 IP

在 `config.py` 中配置代理：

```python
proxy_config = {
    'http': 'http://your-proxy:port',
    'https': 'http://your-proxy:port',
}
```

## 测试步骤

1. **获取有效 Cookie**
   - 按照方法一或方法二获取 `cf_clearance`
   
2. **更新配置文件**
   - 将 cookie 添加到 `config.py`
   
3. **运行测试**
   ```bash
   python test_crawler.py
   ```
   
4. **验证结果**
   - 连接测试应该通过
   - 页面解析应该能找到媒体链接
   - 下载测试应该成功

## 注意事项

1. **Cookie 有效期** - `cf_clearance` 通常有效期为 24 小时
2. **IP 限制** - 频繁请求可能导致 IP 被封
3. **法律合规** - 确保爬取行为符合网站条款和当地法律
4. **资源限制** - 避免对目标服务器造成过大压力

## 替代方案

如果 Cloudflare 绕过太困难，可以考虑：

1. **使用网站提供的 API**（如果有）
2. **寻找镜像网站**
3. **使用 RSS 订阅**
4. **联系网站管理员获取数据**

## 故障排除

### 问题：仍然收到 403 错误
- 检查 cookie 是否过期
- 更新 User-Agent
- 尝试不同的 IP 地址

### 问题：找不到媒体链接
- 检查页面结构是否变化
- 查看 HTML 源代码确认元素选择器
- 使用浏览器开发者工具分析网络请求

### 问题：下载速度慢
- 调整并发数（`max_concurrent`）
- 使用更快的代理
- 优化重试策略

---

**最后更新**: 2024年
**适用网站**: https://ask4porn.cc/
**防护类型**: Cloudflare