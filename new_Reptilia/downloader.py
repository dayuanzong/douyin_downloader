#!/usr/bin/env python3
"""
下载器类 - 处理媒体文件下载
"""
import asyncio
import aiohttp
import aiofiles
import os
from typing import List
from urllib.parse import urlparse

from config import Config

class Downloader:
    """下载器"""
    
    def __init__(self, config: Config):
        """初始化"""
        self.config = config
        self.session: aiohttp.ClientSession = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.create_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close_session()
    
    async def create_session(self):
        """创建aiohttp会话"""
        headers = self.config.headers.copy()
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        connector = aiohttp.TCPConnector(limit=self.config.max_concurrent)
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=timeout,
            connector=connector
        )
    
    async def close_session(self):
        """关闭会话"""
        if self.session:
            await self.session.close()
    
    def get_filename(self, url: str) -> str:
        """从URL提取文件名"""
        parsed = urlparse(url)
        path = parsed.path
        
        # 提取文件名部分
        filename = os.path.basename(path)
        
        # 如果没有扩展名或文件名太短，使用默认名
        if not filename or '.' not in filename or len(filename) < 5:
            # 使用路径的最后一部分或生成哈希名
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"media_{url_hash}.bin"
        
        return filename
    
    async def download_file(self, url: str) -> bool:
        """下载单个文件"""
        filename = self.get_filename(url)
        filepath = os.path.join(self.config.download_dir, filename)
        
        # 如果文件已存在，跳过
        if os.path.exists(filepath):
            print(f"文件已存在: {filename}")
            return True
        
        print(f"正在下载: {filename}")
        
        for attempt in range(self.config.max_retries):
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        
                        async with aiofiles.open(filepath, 'wb') as f:
                            async for chunk in response.content.iter_chunked(self.config.chunk_size):
                                await f.write(chunk)
                                downloaded += len(chunk)
                                
                                # 显示进度
                                if total_size > 0:
                                    percent = (downloaded / total_size) * 100
                                    print(f"  {filename}: {percent:.1f}% ({downloaded}/{total_size} bytes)", end='\r')
                        
                        print(f"  {filename}: 下载完成")
                        return True
                    else:
                        print(f"  {filename}: HTTP错误 {response.status}")
                        
            except aiohttp.ClientError as e:
                print(f"  {filename}: 下载失败 (尝试 {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
            except Exception as e:
                print(f"  {filename}: 未知错误: {e}")
                break
        
        return False
    
    async def download_all(self, urls: List[str]) -> List[str]:
        """并发下载所有文件"""
        if not self.session:
            await self.create_session()
        
        print(f"开始下载 {len(urls)} 个文件...")
        
        # 创建信号量控制并发数
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def download_with_semaphore(url: str):
            async with semaphore:
                return await self.download_file(url)
        
        # 并发下载
        tasks = [download_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = sum(1 for r in results if r is True)
        failed_count = len(urls) - success_count
        
        print(f"下载完成: {success_count} 成功, {failed_count} 失败")
        
        # 返回成功的文件列表
        successful_files = []
        for url, result in zip(urls, results):
            if result is True:
                filename = self.get_filename(url)
                successful_files.append(filename)
        
        return successful_files