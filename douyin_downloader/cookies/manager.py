import re
from pathlib import Path

class CookieManager:
    """
    一个用于管理和提供抖音 Cookie 的类。
    """

    def __init__(self, curl_file: Path):
        """
        初始化 CookieManager。

        :param curl_file: 包含 cURL 命令的文件的路径。
        """
        self.curl_file = curl_file
        self._cookie = None
        self._last_mtime = 0

    def _is_file_updated(self) -> bool:
        """
        检查 cURL 文件自上次读取以来是否已被修改。

        :return: 如果文件已更新，则返回 True，否则返回 False。
        """
        try:
            mtime = self.curl_file.stat().st_mtime
            if mtime > self._last_mtime:
                self._last_mtime = mtime
                return True
            return False
        except FileNotFoundError:
            return True

    def _parse_cookie_from_curl(self) -> str | None:
        """
        从 cURL 命令字符串中解析 Cookie。

        :return: 解析出的 Cookie 字符串，如果未找到则返回 None。
        """
        try:
            curl_command = self.curl_file.read_text(encoding='utf-8')
            
            # 逐行查找包含 -b 或 --cookie 的行
            for line in curl_command.split('\n'):
                line = line.strip()
                if line.startswith('-b') or line.startswith('--cookie'):
                    # 提取cookie部分
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
                        
                        # 移除所有 ^ 转义字符
                        cookie_part = cookie_part.replace('^', '')
                        return cookie_part
            
            return None
        except FileNotFoundError:
            return None

    def get_cookie(self) -> str | None:
        """
        获取 Cookie。如果 cURL 文件已更新，则重新加载。

        :return: Cookie 字符串，如果无法获取则返回 None。
        """
        if self._is_file_updated() or not self._cookie:
            self._cookie = self._parse_cookie_from_curl()
        return self._cookie
