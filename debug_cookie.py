#!/usr/bin/env python3
"""
调试Cookie解析问题的脚本
"""
import sys
import re
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 读取cURL文件内容
curl_file_path = project_root / "samples" / "cURL.txt"
print(f"读取文件: {curl_file_path}")

try:
    curl_content = curl_file_path.read_text(encoding='utf-8')
    print(f"文件内容长度: {len(curl_content)} 字符")
    
    # 打印前几行
    lines = curl_content.split('\n')
    print("\n文件前10行:")
    for i, line in enumerate(lines[:10], 1):
        print(f"{i}: {line}")
    
    # 查找包含 -b 或 --cookie 的行
    cookie_lines = [line for line in lines if line.strip().startswith(('-b', '--cookie'))]
    print(f"\n找到 {len(cookie_lines)} 个cookie行:")
    for i, line in enumerate(cookie_lines, 1):
        print(f"Cookie行 {i}: {line}")
    
    # 测试不同的正则表达式模式
    patterns = [
        r'(?:-b|--cookie)\s+\\^"([^\\^"]+)\\\^"',  # PowerShell格式
        r'(?:-b|--cookie)\s+["\']([^"\']+)["\']',    # 标准格式
        r'(?:-b|--cookie)\s+([^\s]+)',                 # 简单格式
    ]
    
    print("\n测试正则表达式匹配:")
    for i, pattern in enumerate(patterns, 1):
        print(f"\n模式 {i}: {pattern}")
        match = re.search(pattern, curl_content, re.IGNORECASE)
        if match:
            print(f"  匹配成功: {match.group(0)}")
            print(f"  Cookie值: {match.group(1)}")
            cookie_value = match.group(1)
            # 检查是否包含关键cookie字段
            key_fields = ['sessionid', 'sid_tt', 'sid_guard', 'ttwid']
            for field in key_fields:
                if field in cookie_value:
                    print(f"  包含 {field}: 是")
                else:
                    print(f"  包含 {field}: 否")
        else:
            print("  匹配失败")
    
    # 手动解析方法
    print("\n手动解析方法:")
    for line in lines:
        line = line.strip()
        if line.startswith('-b') or line.startswith('--cookie'):
            print(f"处理行: {line}")
            # 尝试分割参数
            parts = line.split(' ', 1)
            if len(parts) > 1:
                cookie_part = parts[1].strip()
                print(f"Cookie部分: {cookie_part}")
                
                # 处理PowerShell转义
                if cookie_part.startswith('^"'):
                    cookie_part = cookie_part[2:]  # 移除 ^"
                    if cookie_part.endswith('^"'):
                        cookie_part = cookie_part[:-2]  # 移除末尾 ^"
                    elif cookie_part.endswith('"'):
                        cookie_part = cookie_part[:-1]  # 移除末尾 "
                elif cookie_part.startswith('"'):
                    cookie_part = cookie_part[1:]  # 移除 "
                    if cookie_part.endswith('"'):
                        cookie_part = cookie_part[:-1]  # 移除末尾 "
                
                # 移除所有 ^ 转义字符
                cookie_part = cookie_part.replace('^', '')
                print(f"处理后Cookie: {cookie_part}")
                
                # 检查关键字段
                key_fields = ['sessionid', 'sid_tt', 'sid_guard', 'ttwid']
                for field in key_fields:
                    if field in cookie_part:
                        print(f"  包含 {field}: 是")
                    else:
                        print(f"  包含 {field}: 否")
                break
            
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()