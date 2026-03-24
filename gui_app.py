import asyncio
import os
from pathlib import Path
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from douyin_downloader.api.client import DouyinAPIClient
from douyin_downloader.cookies.manager import CookieManager
from douyin_downloader.downloader.downloader import Downloader
from douyin_downloader.utils.sec_user_id_extractor import extract_sec_user_id
from gui_downloader import GUIDownloader

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入下载器相关模块


class DouyinDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("抖音视频下载器")
        self.root.geometry("400x500")
        self.root.minsize(600, 400)
        
        # 下载状态变量
        self.is_downloading = False
        self.download_thread = None
        self.download_stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0,
            'current_file': '',
            'current_progress': 0,
            'download_speed': 0,
            'start_time': 0
        }
        
        # 下载队列管理
        self.download_queue = []  # 存储下载任务信息
        self.current_downloads = {}  # 当前正在下载的任务
        
        # 输入记录文件
        self.input_log_file = Path("input_history.txt")
        
        self.setup_ui()
        
    def setup_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="抖音视频下载器", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # 输入区域
        input_frame = ttk.LabelFrame(main_frame, text="下载设置", padding="10")
        input_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)
        
        # URL输入
        ttk.Label(input_frame, text="作者主页URL:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(input_frame, textvariable=self.url_var, width=50)
        url_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        # 保存目录选择
        ttk.Label(input_frame, text="保存目录:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.dir_var = tk.StringVar(value=os.path.join(os.getcwd(), "downloads"))
        dir_frame = ttk.Frame(input_frame)
        dir_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        dir_frame.columnconfigure(0, weight=1)
        
        dir_entry = ttk.Entry(dir_frame, textvariable=self.dir_var)
        dir_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        browse_btn = ttk.Button(dir_frame, text="浏览", width=8, 
                               command=self.browse_directory)
        browse_btn.grid(row=0, column=1, padx=(5, 0))
        
        # cURL文件选择
        ttk.Label(input_frame, text="cURL文件:").grid(row=2, column=0, sticky=tk.W, pady=2)
        default_curl_path = "C:/Users/123456/Desktop/douyin-downloader/samples/cURL.txt"
        self.curl_var = tk.StringVar(value=default_curl_path)
        curl_frame = ttk.Frame(input_frame)
        curl_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        curl_frame.columnconfigure(0, weight=1)
        
        curl_entry = ttk.Entry(curl_frame, textvariable=self.curl_var)
        curl_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        curl_browse_btn = ttk.Button(curl_frame, text="选择", width=8,
                                    command=self.browse_curl_file)
        curl_browse_btn.grid(row=0, column=1, padx=(5, 0))
        
        # 控制按钮区域
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, pady=(0, 10))
        
        self.start_btn = ttk.Button(control_frame, text="开始下载", 
                                   command=self.start_download)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_btn = ttk.Button(control_frame, text="停止", 
                                  command=self.stop_download, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
        
        # 显示区域 - 使用Notebook实现多标签页
        display_notebook = ttk.Notebook(main_frame)
        display_notebook.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 下载队列标签页
        queue_frame = ttk.Frame(display_notebook, padding="5")
        display_notebook.add(queue_frame, text="下载队列")
        
        # 队列操作按钮框架
        queue_controls = ttk.Frame(queue_frame)
        queue_controls.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Button(queue_controls, text="清空队列", command=self.clear_queue).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(queue_controls, text="暂停选中", command=self.pause_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(queue_controls, text="继续选中", command=self.resume_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(queue_controls, text="删除选中", command=self.delete_selected).pack(side=tk.LEFT)
        
        # 下载队列表格
        columns = ("filename", "status", "progress", "speed", "size", "error")
        self.queue_tree = ttk.Treeview(queue_frame, columns=columns, show="headings", height=12)
        
        # 设置列标题
        self.queue_tree.heading("filename", text="文件名")
        self.queue_tree.heading("status", text="状态")
        self.queue_tree.heading("progress", text="进度")
        self.queue_tree.heading("speed", text="速度")
        self.queue_tree.heading("size", text="大小")
        self.queue_tree.heading("error", text="错误信息")
        
        # 设置列宽度
        self.queue_tree.column("filename", width=180)
        self.queue_tree.column("status", width=80)
        self.queue_tree.column("progress", width=80)
        self.queue_tree.column("speed", width=80)
        self.queue_tree.column("size", width=80)
        self.queue_tree.column("error", width=150)
        
        # 添加滚动条
        queue_scrollbar = ttk.Scrollbar(queue_frame, orient=tk.VERTICAL, command=self.queue_tree.yview)
        self.queue_tree.configure(yscrollcommand=queue_scrollbar.set)
        
        self.queue_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        queue_scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        
        # 绑定双击事件查看详情
        self.queue_tree.bind("<Double-1>", self.show_item_details)
        
        queue_frame.columnconfigure(0, weight=1)
        queue_frame.rowconfigure(1, weight=1)
        
        # 日志标签页
        log_frame = ttk.Frame(display_notebook, padding="5")
        display_notebook.add(log_frame, text="日志")
        
        # 日志文本框
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=15)
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # 状态栏
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(status_frame, textvariable=self.status_var)
        status_label.pack(side=tk.LEFT)
        
        # 进度显示区域
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # 进度条
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # 进度文本
        self.progress_text = tk.StringVar()
        self.progress_text.set("等待开始...")
        progress_label = ttk.Label(progress_frame, textvariable=self.progress_text, width=30)
        progress_label.pack(side=tk.RIGHT)
        
    def add_sample_data(self):
        """添加示例数据到下载队列（测试用）"""
        sample_data = [
            ("video_001.mp4", "等待中", "0%", "-", "-", "-"),
            ("video_002.mp4", "下载中", "45%", "1.2MB/s", "15.2MB", "-"),
            ("video_003.mp4", "已完成", "100%", "-", "12.8MB", "-"),
            ("video_004.mp4", "错误", "0%", "-", "-", "网络连接失败")
        ]
        
        for data in sample_data:
            self.queue_tree.insert("", tk.END, values=data)
    
    def browse_directory(self):
        """浏览选择保存目录"""
        directory = filedialog.askdirectory(initialdir=self.dir_var.get())
        if directory:
            self.dir_var.set(directory)
    
    def browse_curl_file(self):
        """浏览选择cURL文件"""
        file_path = filedialog.askopenfilename(
            initialdir=os.getcwd(),
            title="选择cURL文件",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            self.curl_var.set(file_path)
    
    def log_user_input(self, url, save_dir, curl_file):
        """记录用户输入到文件"""
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] URL: {url or '未提供'}, 保存目录: {save_dir}, cURL文件: {curl_file or '未提供'}\n"
            
            with open(self.input_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
                
            self.log(f"输入已记录: URL={url or '无'}, cURL文件={curl_file or '无'}")
        except Exception as e:
            self.log(f"记录输入时出错: {e}")
    
    def start_download(self):
        """开始下载"""
        if self.is_downloading:
            return
            
        # 验证输入
        url = self.url_var.get().strip()
        save_dir = self.dir_var.get().strip()
        curl_file = self.curl_var.get().strip()
        
        # 验证输入：至少需要URL或cURL文件
        if not url and not curl_file:
            messagebox.showerror("错误", "请输入作者主页URL或选择cURL文件")
            return
            
        if not save_dir:
            messagebox.showerror("错误", "请选择保存目录")
            return
            
        # 记录用户输入
        self.log_user_input(url, save_dir, curl_file)
            
        # 创建保存目录（如果不存在）
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法创建保存目录: {e}")
            return
        
        # 准备参数
        curl_file = self.curl_var.get().strip() or None
        
        # 更新UI状态
        self.is_downloading = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_var.set("下载中...")
        
        # 在后台线程中运行下载
        self.download_thread = threading.Thread(
            target=self.run_download,
            args=(url, save_dir, curl_file),
            daemon=True
        )
        self.download_thread.start()
    
    def update_progress(self, stats):
        """更新进度显示"""
        self.download_stats = stats
        
        # 更新进度条
        if stats['total'] > 0:
            overall_progress = ((stats['completed'] + stats['failed'] + stats['skipped']) / stats['total']) * 100
            self.progress_bar['value'] = overall_progress
        
        # 更新进度文本
        if stats['current_file']:
            # 当前文件下载中
            speed_text = f"{stats['download_speed'] / 1024:.1f} KB/s" if stats['download_speed'] > 0 else "计算中..."
            progress_text = f"正在下载: {stats['current_file']} ({stats['current_progress']:.1f}%) - {speed_text}"
        else:
            # 总体进度
            progress_text = f"已完成: {stats['completed']}/{stats['total']} | 失败: {stats['failed']} | 跳过: {stats['skipped']}"
        
        self.progress_text.set(progress_text)
        
        # 更新状态栏
        if stats['total'] > 0:
            elapsed_time = time.time() - stats['start_time']
            status_text = f"下载中 - 总计: {stats['total']} | 已完成: {stats['completed']} | 用时: {elapsed_time:.1f}s"
            self.status_var.set(status_text)
    
    def extract_sec_user_id_from_curl(self, curl_file_path):
        """从cURL文件中提取sec_user_id和作者主页链接"""
        try:
            with open(curl_file_path, 'r', encoding='utf-8') as file:
                curl_content = file.read()
            
            # 在cURL内容中查找sec_user_id
            sec_user_id_pattern = r'sec_user_id=([^&\s]+)'
            match = re.search(sec_user_id_pattern, curl_content)
            if match:
                sec_user_id = match.group(1).replace('^', '')
                
                # 尝试提取作者主页链接
                author_url_pattern = r'https://www\.douyin\.com/user/[^\s\'\"]+'
                author_match = re.search(author_url_pattern, curl_content)
                author_url = author_match.group(0).replace('^', '') if author_match else None
                
                return sec_user_id, author_url
            
            # 如果没有找到，尝试在cookie中查找
            cookie_pattern = r'Cookie:[^\n]*sec_user_id=([^;\s]+)'
            match = re.search(cookie_pattern, curl_content, re.IGNORECASE)
            if match:
                sec_user_id = match.group(1).replace('^', '')
                
                # 尝试提取作者主页链接
                author_url_pattern = r'https://www\.douyin\.com/user/[^\s\'\"]+'
                author_match = re.search(author_url_pattern, curl_content)
                author_url = author_match.group(0).replace('^', '') if author_match else None
                
                return sec_user_id, author_url
                
            return None, None
        except Exception as e:
            self.log(f"读取cURL文件错误: {e}")
            return None, None

    def run_download(self, url, save_dir, curl_file):
        """运行下载任务"""
        try:
            self.log("下载任务开始执行...")
            self.log(f"URL: {url}")
            self.log(f"保存目录: {save_dir}")
            if curl_file:
                self.log(f"cURL文件: {curl_file}")
            
            # 创建保存目录
            download_dir = Path(save_dir)
            download_dir.mkdir(exist_ok=True)
            
            # 初始化组件
            curl_path = Path(curl_file) if curl_file else None
            cookie_manager = CookieManager(curl_path)
            api_client = DouyinAPIClient(cookie_manager, error_callback=lambda error: self.log(f"API错误: {error}"))
            
            # 使用支持进度回调的下载器
            downloader = GUIDownloader(
                api_client, 
                download_dir,
                progress_callback=lambda stats: self.root.after(0, self.update_progress, stats),
                error_callback=lambda error: self.root.after(0, self.handle_download_error, error),
                queue_init_callback=lambda file_list: self.root.after(0, self.init_download_queue, file_list),
                queue_update_callback=lambda filename, status, progress, speed, size="-", error="-": self.root.after(0, self.update_queue_item, filename, status, progress, speed, size, error)
            )
            
            # 提取 sec_user_id 和 author_url
            sec_user_id = None
            author_url = None
            if url:
                sec_user_id = extract_sec_user_id(url)
                author_url = url
            elif curl_file:
                sec_user_id, author_url = self.extract_sec_user_id_from_curl(curl_file)
            
            if not sec_user_id:
                error_msg = "无法从链接或cURL文件中提取 sec_user_id，请检查输入是否正确。"
                self.log(f"错误: {error_msg}")
                self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
                return
            
            self.log(f"成功提取 sec_user_id: {sec_user_id}")
            if author_url:
                self.log(f"作者主页链接: {author_url}")
            self.log(f"开始下载该作者的所有作品...")
            
            # 运行异步下载任务
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(downloader.download_user_posts(sec_user_id))
                self.log("所有作品下载完成！")
                self.root.after(0, lambda: self.progress_text.set("下载完成!"))
            except Exception as e:
                self.log(f"下载过程中发生错误: {e}")
            finally:
                loop.close()
            
        except Exception as e:
            self.log(f"下载错误: {e}")
        finally:
            # 恢复UI状态
            self.root.after(0, self.download_completed)
    
    def download_completed(self):
        """下载完成回调"""
        self.is_downloading = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("下载完成")
    
    def stop_download(self):
        """停止下载"""
        if self.is_downloading:
            self.is_downloading = False
            self.status_var.set("正在停止...")
            # 这里需要实现真正的停止逻辑
            self.log("用户请求停止下载")
            self.download_completed()
    
    def log(self, message):
        """添加日志消息，同时输出到UI和控制台"""
        # 输出到控制台
        print(message)
        
        # 输出到UI日志
        def update_log():
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
        
        self.root.after(0, update_log)
    
    # 队列管理方法
    def clear_queue(self):
        """清空下载队列"""
        if messagebox.askyesno("确认", "确定要清空下载队列吗？"):
            for item in self.queue_tree.get_children():
                self.queue_tree.delete(item)
            self.download_queue.clear()
            self.log("下载队列已清空")
    
    def pause_selected(self):
        """暂停选中的下载任务"""
        selected = self.queue_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择要暂停的任务")
            return
        
        for item in selected:
            values = self.queue_tree.item(item, 'values')
            if values[1] == "下载中":
                self.queue_tree.set(item, "status", "已暂停")
                self.log(f"已暂停任务: {values[0]}")
    
    def resume_selected(self):
        """继续选中的下载任务"""
        selected = self.queue_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择要继续的任务")
            return
        
        for item in selected:
            values = self.queue_tree.item(item, 'values')
            if values[1] == "已暂停":
                self.queue_tree.set(item, "status", "等待中")
                self.log(f"已继续任务: {values[0]}")
    
    def delete_selected(self):
        """删除选中的下载任务"""
        selected = self.queue_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择要删除的任务")
            return
        
        if messagebox.askyesno("确认", f"确定要删除选中的 {len(selected)} 个任务吗？"):
            for item in selected:
                values = self.queue_tree.item(item, 'values')
                self.queue_tree.delete(item)
                self.log(f"已删除任务: {values[0]}")
    
    def show_item_details(self, event):
        """显示选中任务的详细信息"""
        selected = self.queue_tree.selection()
        if not selected:
            return
        
        item = selected[0]
        values = self.queue_tree.item(item, 'values')
        
        # 创建详情对话框
        detail_window = tk.Toplevel(self.root)
        detail_window.title("任务详情")
        detail_window.geometry("400x300")
        
        # 详情内容
        detail_text = tk.Text(detail_window, wrap=tk.WORD)
        detail_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        info = f"文件名: {values[0]}\n"
        info += f"状态: {values[1]}\n"
        info += f"进度: {values[2]}\n"
        info += f"速度: {values[3]}\n"
        info += f"大小: {values[4]}\n"
        info += f"错误信息: {values[5]}\n"
        
        detail_text.insert(tk.END, info)
        detail_text.config(state=tk.DISABLED)
        
        # 关闭按钮
        ttk.Button(detail_window, text="关闭", command=detail_window.destroy).pack(pady=10)
    
    def init_download_queue(self, file_list):
        """初始化下载队列，添加所有文件项"""
        def update():
            # 清空现有队列
            for item in self.queue_tree.get_children():
                self.queue_tree.delete(item)
            self.download_queue.clear()
            
            # 添加新的文件项到队列
            for filename in file_list:
                self.queue_tree.insert("", tk.END, values=(filename, "等待中", "0%", "-", "-", "-"))
                self.download_queue.append({
                    'filename': filename,
                    'status': "等待中",
                    'progress': "0%",
                    'speed': "-",
                    'size': "-",
                    'error': "-"
                })
            
            self.log(f"已初始化下载队列，共 {len(file_list)} 个文件")
        
        self.root.after(0, update)
    
    def update_queue_item(self, filename, status, progress, speed, size="-", error="-"):
        """更新队列中的任务状态"""
        def update():
            # 查找对应的任务项
            for item in self.queue_tree.get_children():
                values = self.queue_tree.item(item, 'values')
                if values[0] == filename:
                    # 如果状态变为"已完成"，则移动到队列末尾
                    if status == "已完成":
                        # 删除原项并重新插入到末尾
                        self.queue_tree.delete(item)
                        self.queue_tree.insert("", tk.END, values=(filename, status, progress, speed, size, error))
                    else:
                        # 其他状态只更新值
                        self.queue_tree.set(item, "status", status)
                        self.queue_tree.set(item, "progress", progress)
                        self.queue_tree.set(item, "speed", speed)
                        self.queue_tree.set(item, "size", size)
                        self.queue_tree.set(item, "error", error)
                    break
        
        self.root.after(0, update)
    
    def handle_download_error(self, error_info):
        """处理下载错误"""
        def update():
            filename = error_info.get('filename', '未知文件')
            error_msg = error_info.get('error', '未知错误')
            timestamp = error_info.get('timestamp', '')
            
            # 更新队列中的错误信息
            self.update_queue_item(filename, "错误", "0%", "-", "-", error_msg)
            
            # 记录错误日志
            log_msg = f"错误 [{timestamp}]: {filename} - {error_msg}"
            self.log(log_msg)
            
            # 在状态栏显示错误
            self.status_var.set(f"下载错误: {filename}")
        
        self.root.after(0, update)

def main():
    """启动GUI应用"""
    root = tk.Tk()
    app = DouyinDownloaderGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()