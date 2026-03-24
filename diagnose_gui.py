#!/usr/bin/env python3
"""
诊断GUI应用运行时的问题
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_imports():
    """检查所有必要的导入"""
    print("=== 检查导入 ===")
    
    imports_to_check = [
        "tkinter",
        "tkinter.ttk", 
        "tkinter.filedialog",
        "tkinter.messagebox",
        "threading",
        "asyncio",
        "pathlib",
        "re",
        "time",
        "douyin_downloader.api.client",
        "douyin_downloader.cookies.manager",
        "douyin_downloader.downloader.gui_downloader"
    ]
    
    for import_name in imports_to_check:
        try:
            if "." in import_name:
                # 处理模块.子模块的情况
                module_name, attr_name = import_name.split(".", 1)
                __import__(module_name)
                mod = sys.modules[module_name]
                # 检查子属性
                parts = attr_name.split(".")
                current = mod
                for part in parts:
                    current = getattr(current, part)
                print(f"✅ {import_name}")
            else:
                __import__(import_name)
                print(f"✅ {import_name}")
        except ImportError as e:
            print(f"❌ {import_name}: {e}")
        except AttributeError as e:
            print(f"❌ {import_name}: {e}")

def check_file_paths():
    """检查必要的文件路径"""
    print("\n=== 检查文件路径 ===")
    
    files_to_check = [
        "gui_app.py",
        "douyin_downloader/api/client.py",
        "douyin_downloader/cookies/manager.py", 
        "douyin_downloader/downloader/gui_downloader.py",
        "samples/cURL.txt",
        "samples/作者主页链接.txt"
    ]
    
    for file_path in files_to_check:
        full_path = project_root / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} (不存在)")

def check_sample_files():
    """检查示例文件内容"""
    print("\n=== 检查示例文件内容 ===")
    
    # 检查作者主页链接文件
    sample_url_file = project_root / "samples" / "作者主页链接.txt"
    if sample_url_file.exists():
        content = sample_url_file.read_text(encoding='utf-8').strip()
        print(f"作者主页链接内容: {repr(content)}")
        
        # 检查是否能提取sec_user_id
        from douyin_downloader.main import extract_sec_user_id
        sec_user_id = extract_sec_user_id(content)
        print(f"提取的sec_user_id: {sec_user_id}")
    else:
        print("❌ 作者主页链接文件不存在")
    
    # 检查cURL文件
    curl_file = project_root / "samples" / "cURL.txt"
    if curl_file.exists():
        content = curl_file.read_text(encoding='utf-8')
        print(f"cURL文件大小: {len(content)} 字符")
        
        # 检查是否能提取sec_user_id
        from gui_app import DouyinDownloaderGUI
        gui = None
        try:
            # 创建临时GUI实例来调用方法
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()  # 隐藏窗口
            gui = DouyinDownloaderGUI(root)
            sec_user_id = gui.extract_sec_user_id_from_curl(str(curl_file))
            print(f"从cURL提取的sec_user_id: {sec_user_id}")
        except Exception as e:
            print(f"从cURL提取sec_user_id时出错: {e}")
        finally:
            if gui:
                root.destroy()
    else:
        print("❌ cURL文件不存在")

def simulate_gui_startup():
    """模拟GUI启动过程"""
    print("\n=== 模拟GUI启动 ===")
    
    try:
        import tkinter as tk
        from gui_app import DouyinDownloaderGUI
        
        # 创建根窗口但不显示
        root = tk.Tk()
        root.withdraw()
        
        # 创建GUI实例
        gui = DouyinDownloaderGUI(root)
        print("✅ GUI实例创建成功")
        
        # 检查UI变量
        print(f"URL变量类型: {type(gui.url_var)}")
        print(f"目录变量类型: {type(gui.dir_var)}") 
        print(f"cURL变量类型: {type(gui.curl_var)}")
        
        # 检查方法是否存在
        methods_to_check = [
            'browse_directory', 'browse_curl_file', 'start_download', 
            'stop_download', 'extract_sec_user_id_from_curl', 'run_download'
        ]
        
        for method_name in methods_to_check:
            if hasattr(gui, method_name):
                print(f"✅ 方法 {method_name} 存在")
            else:
                print(f"❌ 方法 {method_name} 不存在")
        
        root.destroy()
        
    except Exception as e:
        print(f"❌ GUI启动失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("GUI应用诊断工具")
    print("=" * 50)
    
    check_imports()
    check_file_paths() 
    check_sample_files()
    simulate_gui_startup()
    
    print("\n" + "=" * 50)
    print("诊断完成！")
    print("如果所有检查都通过，但GUI仍然有问题，请检查：")
    print("1. 运行时错误信息（查看GUI日志）")
    print("2. 网络连接问题")
    print("3. Cookie是否过期")
    print("4. 用户输入是否正确传递")
    print("5. 异步任务是否正常启动")