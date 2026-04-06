# Ask4Porn 爬虫程序

基于抖音下载器架构开发的针对 `ask4porn.cc` 网站的爬虫程序。

## 项目结构

```
new_Reptilia/
├── main.py              # 程序入口
├── config.py            # 配置文件
├── client.py            # 客户端（处理HTTP请求和页面解析）
├── downloader.py        # 下载器（处理文件下载）
├── test_crawler.py      # 测试脚本
├── requirements.txt     # Python依赖
├── CLOUDFLARE_BYPASS_GUIDE.md  # Cloudflare绕过指南
└── README.md            # 本文档
```

## 功能特性

1. **异步处理** - 使用 asyncio 和 aiohttp 实现高性能异步请求
2. **并发下载** - 支持多文件并发下载，可配置并发数
3. **重试机制** - 自动重试失败的请求，可配置重试次数
4. **进度显示** - 实时显示下载进度和状态
5. **错误处理** - 完善的异常处理和日志记录
6. **配置管理** - 通过配置文件管理所有参数

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置程序

编辑 `config.py` 文件：

```python
# 基本配置
base_url = "https://ask4porn.cc"
target_url = "https://ask4porn.cc/onlyfans-itslov3lychick-and-dredd/"

# 请求配置
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...'
}

# 下载配置
download_dir = "downloads"
max_concurrent = 3  # 最大并发数
retry_times = 3     # 重试次数
```

### 3. 处理 Cloudflare 防护

目标网站使用 Cloudflare 防护，需要手动获取 cookie：

1. 使用浏览器访问目标网站
2. 完成 Cloudflare 验证
3. 获取 `cf_clearance` cookie
4. 添加到 `config.py` 的 `cloudflare_cookies` 配置

详细步骤请参考 [CLOUDFLARE_BYPASS_GUIDE.md](CLOUDFLARE_BYPASS_GUIDE.md)

### 4. 运行程序

```bash
python main.py
```

程序会：
1. 连接到目标网站
2. 解析页面获取媒体链接
3. 下载所有媒体文件到 `downloads/` 目录

## 测试

运行测试脚本验证功能：

```bash
python test_crawler.py
```

测试包括：
- 连接测试
- 页面解析测试
- 下载功能测试

## 配置说明

### config.py

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `base_url` | 网站基础URL | `"https://ask4porn.cc"` |
| `target_url` | 目标页面URL | 用户输入 |
| `headers` | HTTP请求头 | 模拟Chrome浏览器 |
| `download_dir` | 下载目录 | `"downloads"` |
| `max_concurrent` | 最大并发数 | `3` |
| `retry_times` | 重试次数 | `3` |
| `timeout` | 请求超时(秒) | `30` |
| `cloudflare_cookies` | Cloudflare cookies | `{}` |

### 自定义配置

可以创建 `config.json` 文件覆盖默认配置：

```json
{
    "download_dir": "my_downloads",
    "max_concurrent": 5,
    "retry_times": 5
}
```

## 与抖音下载器的对比

### 相同点
1. 异步架构设计
2. 并发下载控制
3. 重试机制
4. 进度显示

### 不同点
| 方面 | 抖音下载器 | Ask4Porn爬虫 |
|------|-----------|-------------|
| 目标网站 | 抖音API | ask4porn.cc |
| 反爬机制 | xbogus签名 | Cloudflare防护 |
| 数据获取 | API调用 | HTML页面解析 |
| 验证方式 | Cookie管理 | 手动Cookie获取 |
| 文件类型 | 视频为主 | 图片/视频混合 |

## 开发指南

### 扩展功能

1. **添加新的解析器**
   - 继承 `client.py` 中的解析方法
   - 支持不同页面结构

2. **添加代理支持**
   - 在 `config.py` 中添加代理配置
   - 在 `client.py` 中实现代理连接

3. **添加数据库支持**
   - 记录下载历史
   - 避免重复下载

### 调试技巧

1. **查看日志**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **保存HTML页面**
   ```python
   with open('debug.html', 'w', encoding='utf-8') as f:
       f.write(html_content)
   ```

3. **使用代理调试**
   - Charles/Fiddler 抓包
   - 浏览器开发者工具分析

## 常见问题

### Q: 为什么收到 403 Forbidden 错误？
A: 网站使用了 Cloudflare 防护，需要获取有效的 `cf_clearance` cookie。

### Q: 如何提高下载速度？
A: 增加 `max_concurrent` 值，但注意不要对服务器造成过大压力。

### Q: 下载的文件在哪里？
A: 默认在 `downloads/` 目录，可以在 `config.py` 中修改。

### Q: 如何爬取其他页面？
A: 修改 `config.py` 中的 `target_url`，或运行程序时输入新的URL。

## 注意事项

1. **法律合规** - 遵守目标网站的 robots.txt 和服务条款
2. **频率限制** - 避免过于频繁的请求，防止IP被封
3. **资源使用** - 合理设置并发数，避免占用过多网络资源
4. **数据隐私** - 仅下载公开可访问的内容

## 许可证

本项目仅供学习和技术研究使用。

## 更新日志

- v1.0.0 (2024) - 初始版本，支持基本爬取和下载功能

---

**提示**: 爬虫开发是一个持续的过程，网站结构变化时需要相应调整代码。