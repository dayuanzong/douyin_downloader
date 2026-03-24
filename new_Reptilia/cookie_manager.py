import re
from pathlib import Path
from typing import Dict, Optional


class CookieManager:
    """
    Cookie管理器，参考抖音下载器的实现
    支持从cURL文件或手动配置中获取Cookie
    """

    def __init__(self, curl_file: Optional[Path] = None, cookie_dict: Optional[Dict[str, str]] = None):
        """
        初始化CookieManager
        
        :param curl_file: 包含cURL命令的文件路径
        :param cookie_dict: 手动配置的Cookie字典
        """
        self.curl_file = curl_file
        self.cookie_dict = cookie_dict or {}
        self._cookie = None
        self._last_mtime = 0

    def _is_file_updated(self) -> bool:
        """检查cURL文件是否已更新"""
        if not self.curl_file:
            return False
            
        try:
            mtime = self.curl_file.stat().st_mtime
            if mtime > self._last_mtime:
                self._last_mtime = mtime
                return True
            return False
        except FileNotFoundError:
            return False

    def _parse_cookie_from_curl(self) -> str | None:
        """从cURL命令中解析Cookie"""
        if not self.curl_file:
            return None
            
        try:
            curl_command = self.curl_file.read_text(encoding='utf-8')
            
            # 查找包含Cookie的行
            for line in curl_command.split('\n'):
                line = line.strip()
                if line.startswith('-b') or line.startswith('--cookie'):
                    parts = line.split(' ', 1)
                    if len(parts) > 1:
                        cookie_part = parts[1].strip()
                        
                        # 处理PowerShell转义格式: -b ^"cookie_value^"
                        if cookie_part.startswith('^"'):
                            cookie_part = cookie_part[2:]  # 移除 ^"
                            if cookie_part.endswith('^"'):
                                cookie_part = cookie_part[:-2]  # 移除末尾 ^"
                            elif cookie_part.endswith('"'):
                                cookie_part = cookie_part[:-1]  # 移除末尾 "
                        # 处理标准格式: -b "cookie_value"
                        elif cookie_part.startswith('"'):
                            cookie_part = cookie_part[1:]  # 移除 "
                            if cookie_part.endswith('"'):
                                cookie_part = cookie_part[:-1]  # 移除末尾 "
                        # 处理单引号格式: -b 'cookie_value'
                        elif cookie_part.startswith("'"):
                            cookie_part = cookie_part[1:]  # 移除 '
                            if cookie_part.endswith("'"):
                                cookie_part = cookie_part[:-1]  # 移除末尾 '
                        
                        # 移除所有^转义字符
                        cookie_part = cookie_part.replace('^', '')
                        return cookie_part
            
            return None
        except FileNotFoundError:
            return None

    def get_cookie_string(self) -> Optional[str]:
        """获取Cookie字符串"""
        # 优先使用cURL文件中的Cookie
        if self._is_file_updated() or not self._cookie:
            self._cookie = self._parse_cookie_from_curl()
        
        # 如果没有cURL Cookie，使用手动配置的Cookie
        if not self._cookie and self.cookie_dict:
            self._cookie = self._build_cookie_string()
        
        return self._cookie

    def _build_cookie_string(self) -> str:
        """将Cookie字典转换为字符串格式"""
        cookie_parts = []
        for key, value in self.cookie_dict.items():
            cookie_parts.append(f"{key}={value}")
        return "; ".join(cookie_parts)

    def get_cookie_dict(self) -> Dict[str, str]:
        """获取Cookie字典格式"""
        cookie_string = self.get_cookie_string()
        if not cookie_string:
            return {}
        
        cookies = {}
        for cookie_part in cookie_string.split(';'):
            if '=' in cookie_part:
                key, value = cookie_part.strip().split('=', 1)
                cookies[key] = value
        return cookies

    def set_cookie(self, name: str, value: str) -> None:
        """设置单个Cookie"""
        self.cookie_dict[name] = value
        # 清除缓存的cookie string，强制重新构建
        self._cookie = None

    def update_cookies(self, cookies: Dict[str, str]) -> None:
        """批量更新Cookie"""
        self.cookie_dict.update(cookies)
        self._cookie = None

    def remove_cookie(self, name: str) -> None:
        """删除Cookie"""
        if name in self.cookie_dict:
            del self.cookie_dict[name]
        self._cookie = None

    def clear_cookies(self) -> None:
        """清除所有Cookie"""
        self.cookie_dict.clear()
        self._cookie = None

    def is_valid(self) -> bool:
        """检查Cookie是否有效"""
        cookie_string = self.get_cookie_string()
        return cookie_string is not None and len(cookie_string) > 0

    def validate_cookies(self) -> Dict[str, bool]:
        """验证各个Cookie项的有效性"""
        cookie_dict = self.get_cookie_dict()
        validation = {}
        
        for name, value in cookie_dict.items():
            # 基本的有效性检查
            validation[name] = len(value) > 0 and not value.startswith('deleted')
        
        return validation


# 便捷的Cookie管理器创建函数
def create_cookie_manager(curl_file_path: Optional[str] = None, 
                         cookie_config: Optional[Dict[str, str]] = None) -> CookieManager:
    """创建Cookie管理器实例"""
    curl_file = Path(curl_file_path) if curl_file_path else None
    return CookieManager(curl_file=curl_file, cookie_dict=cookie_config or {})