#!/usr/bin/env python3
"""
配置文件 - Ask4Porn爬虫
"""
import json
import os
from typing import Dict, Optional


class Config:
    """配置类"""
    
    def __init__(self):
        # ====== 基本配置 ======
        self.base_url = "https://ask4porn.cc"
        self.target_url = ""  # 目标页面URL
        
        # ====== Cookie配置 ======
        self.cookie_config = {
            'cf_clearance': '',  # 从cURL文件或手动获取
        }
        self.curl_file_path = "cURL.txt"
        
        # ====== 请求配置 ======
        self.headers = {
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
        
        # ====== 下载配置 ======
        self.download_dir = "downloads"
        self.max_concurrent = 1  # 单一视频下载
        self.max_retries = 3
        self.timeout = 30
        self.chunk_size = 8192
        
        # ====== 视频质量配置 ======
        self.video_quality_config = {
            'max_resolution': True,  # 自动选择最高分辨率
            'prefer_formats': ['mp4', 'webm'],  # 优先格式
            'min_resolution': '720p',  # 最低分辨率要求
            'ad_filter_enabled': True,  # 启用广告过滤
            'ad_file_size_threshold': 10 * 1024 * 1024,  # 10MB阈值
        }
        
        # ====== Cloudflare配置 ======
        self.cf_clearance = None
        
        # ====== 代理配置 ======
        self.proxy = None
        
        # 确保下载目录存在
        os.makedirs(self.download_dir, exist_ok=True)
    
    def save(self, filepath: str = "config.json"):
        """保存配置到文件"""
        config_data = {
            'target_url': self.target_url,
            'cookie_config': self.cookie_config,
            'curl_file_path': self.curl_file_path,
            'download_dir': self.download_dir,
            'max_concurrent': self.max_concurrent,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'chunk_size': self.chunk_size,
            'video_quality_config': self.video_quality_config,
            'cf_clearance': self.cf_clearance,
            'proxy': self.proxy,
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str = "config.json"):
        """从文件加载配置"""
        config = cls()
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(config, key):
                            setattr(config, key, value)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
        return config
    
    def get_effective_headers(self) -> Dict[str, str]:
        """获取合并了Cookie的有效请求头"""
        headers = self.headers.copy()
        
        # 添加Cookie到请求头
        if self.cookie_config:
            cookie_string = "; ".join([f"{k}={v}" for k, v in self.cookie_config.items() if v])
            if cookie_string:
                headers['Cookie'] = cookie_string
        
        return headers
    
    def get_video_quality_options(self) -> Dict:
        """获取视频质量配置选项"""
        return self.video_quality_config.copy()
    
    def set_cookie(self, name: str, value: str):
        """设置Cookie"""
        self.cookie_config[name] = value
    
    def set_target_url(self, url: str):
        """设置目标URL"""
        self.target_url = url


# 创建默认配置实例
config = Config()