from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from douyin_downloader.gui.persistence import FileLogger, PreferencesStore
from douyin_downloader.gui.state import GUIState
from douyin_downloader.gui.views import MainWindowView
from douyin_downloader.models import DownloadCallbacks, DownloadRequest
from douyin_downloader.paths import GUI_STATE_FILE, INPUT_HISTORY_FILE, LOG_FILE, ensure_runtime_dir
from douyin_downloader.services.browser_auth_service import BrowserAuthService, BrowserCookieImportResult
from douyin_downloader.services.download_service import DownloadService


class MainWindowController:
    def __init__(self, root: tk.Tk, state: GUIState, view: MainWindowView, service: DownloadService):
        self.root = root
        self.state = state
        self.view = view
        self.service = service
        ensure_runtime_dir()
        self.input_log_file = INPUT_HISTORY_FILE
        self.preferences_store = PreferencesStore(GUI_STATE_FILE)
        self.file_logger = FileLogger(LOG_FILE)
        self.download_thread = None
        self.browser_import_thread = None
        self.download_queue: list[dict] = []
        self._save_after_id = None
        self.browser_auth_service = BrowserAuthService(
            preferred_executable=Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
        )

        self._bind_actions()
        self._reset_run_logs()
        self._load_preferences()
        self._bind_persistence()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _bind_actions(self) -> None:
        for key, button in self.view.sidebar_buttons.items():
            button.configure(command=lambda current=key: self.switch_section(current))

        for key, button in self.view.top_tab_buttons.items():
            button.configure(command=lambda current=key: self.switch_workspace_tab(current))

        self.view.browse_dir_button.configure(command=self.browse_directory)
        self.view.import_browser_button.configure(command=self.import_from_browser)
        self.view.import_curl_button.configure(command=self.import_curl_text)
        self.view.clear_curl_button.configure(command=self.clear_auth_input)
        self.view.start_button.configure(command=self.start_download)
        self.view.stop_button.configure(command=self.stop_download)
        self.view.clear_queue_button.configure(command=self.clear_queue)
        self.view.pause_button.configure(command=self.pause_selected)
        self.view.resume_button.configure(command=self.resume_selected)
        self.view.delete_button.configure(command=self.delete_selected)
        self.view.queue_tree.bind("<Double-1>", self.show_item_details)

    def switch_section(self, section_key: str) -> None:
        self.state.active_section = section_key
        self.view.show_section(section_key)

    def switch_workspace_tab(self, tab_key: str) -> None:
        self.state.active_tab = tab_key
        self.view.show_workspace_panel(tab_key)
        if self.state.active_section != "workspace":
            self.switch_section("workspace")

    def browse_directory(self) -> None:
        directory = filedialog.askdirectory(initialdir=self.state.save_dir_var.get())
        if directory:
            self.state.save_dir_var.set(directory)

    def import_curl_text(self) -> None:
        file_path = filedialog.askopenfilename(
            initialdir=str(Path.cwd()),
            title="选择 cURL 文本文件",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("错误", f"无法读取 cURL 文件: {exc}")
            return

        self.view.set_curl_text(content)
        self.view.update_metric("auth", "已导入文本")
        self.log(f"已导入 cURL 文件: {file_path}")
        self.save_preferences()
        self.switch_workspace_tab("auth")

    def clear_auth_input(self) -> None:
        self.view.set_curl_text("")
        self.view.update_metric("auth", "等待输入")
        self.save_preferences()

    def import_from_browser(self) -> None:
        if self.browser_import_thread and self.browser_import_thread.is_alive():
            return

        self.switch_workspace_tab("auth")
        self.view.import_browser_button.configure(state=tk.DISABLED)
        self.state.status_var.set("等待浏览器登录导入...")
        self.view.update_metric("auth", "浏览器登录中")
        self.log("准备通过浏览器登录导入 Cookie。")

        self.browser_import_thread = threading.Thread(
            target=self._run_browser_import,
            daemon=True,
        )
        self.browser_import_thread.start()

    def _run_browser_import(self) -> None:
        try:
            result = self.browser_auth_service.import_cookie_text(log_callback=self.log)
            self.root.after(0, lambda: self._finish_browser_import(result))
        except Exception as exc:
            self.root.after(0, lambda: self._handle_browser_import_error(exc))
        finally:
            self.root.after(0, lambda: self.view.import_browser_button.configure(state=tk.NORMAL))

    def _finish_browser_import(self, result: BrowserCookieImportResult) -> None:
        self.view.set_curl_text(result.cookie_text)
        self.view.update_metric("auth", f"已导入 {result.cookie_count} 个 Cookie")
        self.state.status_var.set(f"已从 {result.source} 导入认证")
        self.log(
            f"浏览器导入完成：{result.source}，共读取 {result.cookie_count} 个 Cookie。"
        )
        self.save_preferences()
        messagebox.showinfo(
            "导入完成",
            f"已从 {result.source} 导入 {result.cookie_count} 个 Cookie，现在可以直接开始下载。",
        )

    def _handle_browser_import_error(self, exc: Exception) -> None:
        self.view.update_metric("auth", "导入失败")
        self.state.status_var.set("浏览器导入失败")
        error_message = self._format_exception_message(exc, "浏览器导入失败")
        self.log(f"浏览器导入失败: {error_message}")
        messagebox.showerror("导入失败", error_message)

    def build_request(self) -> DownloadRequest:
        selected_mode = self.state.download_mode_var.get().strip() or "author"
        input_url = (
            self.state.author_url_var.get().strip()
            if selected_mode == "author"
            else self.state.aweme_url_var.get().strip()
        )
        return DownloadRequest(
            url=input_url,
            save_dir=Path(self.state.save_dir_var.get().strip()),
            curl_text=self.view.get_curl_text(),
        )

    def start_download(self) -> None:
        if self.state.is_downloading:
            return

        save_dir_raw = self.state.save_dir_var.get().strip()
        if not save_dir_raw:
            messagebox.showerror("错误", "请选择保存目录。")
            return

        request = self.build_request()
        if not request.has_auth_input:
            if self.state.download_mode_var.get() == "aweme":
                messagebox.showerror("错误", "请输入作品分享口令、短链或作品链接。")
            else:
                messagebox.showerror("错误", "请输入作者主页 URL。")
            return

        try:
            request.save_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showerror("错误", f"无法创建保存目录: {exc}")
            return

        self._reset_run_logs()
        self.log_user_input(request)
        self.state.is_downloading = True
        self.view.start_button.configure(state=tk.DISABLED)
        self.view.stop_button.configure(state=tk.NORMAL)
        self.state.status_var.set("下载中...")
        self.view.update_metric("status", "下载中")
        self.view.update_metric("auth", "已配置")

        callbacks = DownloadCallbacks(
            progress_callback=lambda stats: self.root.after(0, self.update_progress, stats),
            error_callback=lambda error: self.root.after(0, self.handle_download_error, error),
            queue_init_callback=lambda file_list: self.root.after(0, self.init_download_queue, file_list),
            queue_update_callback=lambda filename, status, progress, speed, size, error: self.root.after(
                0, self.update_queue_item, filename, status, progress, speed, size, error
            ),
            log_callback=self.log,
        )

        self.download_thread = threading.Thread(
            target=self._run_download_task,
            args=(request, callbacks),
            daemon=True,
        )
        self.download_thread.start()

    def _run_download_task(self, request: DownloadRequest, callbacks: DownloadCallbacks) -> None:
        success = False
        try:
            self.service.run_gui_download(request, callbacks)
            success = True
            self.root.after(0, lambda: self.state.progress_var.set("下载完成!"))
        except Exception as exc:
            error_message = self._format_exception_message(exc, "下载失败")
            self.log(f"下载错误: {error_message}")
            self.root.after(0, lambda: messagebox.showerror("错误", error_message))
        finally:
            self.root.after(0, lambda: self.download_completed(success))

    def update_progress(self, stats: dict) -> None:
        if stats["total"] > 0:
            completed = stats["completed"] + stats["failed"] + stats["skipped"]
            overall_progress = completed / stats["total"] * 100
            self.view.progress_bar["value"] = overall_progress

        if stats.get("current_file"):
            speed = stats.get("download_speed", 0)
            speed_text = f"{speed / 1024:.1f} KB/s" if speed > 0 else "计算中..."
            progress_text = f"正在下载: {stats['current_file']} ({stats['current_progress']:.1f}%) - {speed_text}"
        else:
            progress_text = (
                f"已完成: {stats['completed']}/{stats['total']} | "
                f"失败: {stats['failed']} | 跳过: {stats['skipped']}"
            )

        self.state.progress_var.set(progress_text)
        self.state.status_var.set(
            f"下载中 - 总计: {stats['total']} | 已完成: {stats['completed']} | 失败: {stats['failed']}"
        )
        self.view.update_metric("queue", f"{stats['total']} 个任务")

    def download_completed(self, success: bool = True) -> None:
        self.state.is_downloading = False
        self.view.start_button.configure(state=tk.NORMAL)
        self.view.stop_button.configure(state=tk.DISABLED)
        if success:
            self.state.status_var.set("下载完成")
            self.view.update_metric("status", "已完成")
        else:
            self.state.status_var.set("下载失败")
            self.view.update_metric("status", "失败")

    def stop_download(self) -> None:
        if not self.state.is_downloading:
            return
        self.state.status_var.set("停止请求已记录")
        self.log("用户请求停止下载，当前取消能力将在后续任务取消器接入后完善。")
        messagebox.showinfo("提示", "当前版本已经完成模块重构，但真正的下载中断还未接入。")

    def log(self, message: str) -> None:
        print(message)
        self.file_logger.write(message)
        self.root.after(0, lambda: self.view.append_log(message))

    def _reset_run_logs(self) -> None:
        self.file_logger.reset()
        self.view.clear_logs()

    def log_user_input(self, request: DownloadRequest) -> None:
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            curl_summary = f"内联 cURL 文本 {len(request.curl_text.strip())} 字符" if request.curl_text.strip() else "未提供"
            download_mode = self.state.download_mode_var.get().strip() or "author"
            with self.input_log_file.open("w", encoding="utf-8") as file:
                file.write(
                    f"[{timestamp}] 模式: {download_mode}, URL: {request.url or '未提供'}, 保存目录: {request.save_dir}, cURL: {curl_summary}\n"
                )
        except Exception as exc:
            self.log(f"记录输入时出错: {exc}")

    def _bind_persistence(self) -> None:
        self.state.author_url_var.trace_add("write", self._schedule_preferences_save)
        self.state.aweme_url_var.trace_add("write", self._schedule_preferences_save)
        self.state.download_mode_var.trace_add("write", self._schedule_preferences_save)
        self.state.save_dir_var.trace_add("write", self._schedule_preferences_save)
        self.view.curl_text.bind("<<Modified>>", self._on_curl_text_modified)

    def _on_curl_text_modified(self, _event) -> None:
        if not self.view.curl_text.edit_modified():
            return
        self.view.curl_text.edit_modified(False)
        self._schedule_preferences_save()

    def _schedule_preferences_save(self, *_args) -> None:
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
        self._save_after_id = self.root.after(400, self.save_preferences)

    def save_preferences(self) -> None:
        self._save_after_id = None
        data = {
            "author_url": self.state.author_url_var.get().strip(),
            "aweme_url": self.state.aweme_url_var.get().strip(),
            "download_mode": self.state.download_mode_var.get().strip(),
            "save_dir": self.state.save_dir_var.get().strip(),
            "curl_text": self.view.get_curl_text(),
            "active_section": self.state.active_section,
            "active_tab": self.state.active_tab,
        }
        try:
            self.preferences_store.save(data)
        except OSError as exc:
            self.log(f"保存界面参数失败: {exc}")

    def _load_preferences(self) -> None:
        data = self.preferences_store.load()
        if not data:
            return
        self.state.author_url_var.set(data.get("author_url", data.get("url", "")))
        self.state.aweme_url_var.set(data.get("aweme_url", ""))
        self.state.download_mode_var.set(data.get("download_mode", "author"))
        if data.get("save_dir"):
            self.state.save_dir_var.set(data["save_dir"])
        if data.get("curl_text"):
            self.view.set_curl_text(data["curl_text"])
            self.view.update_metric("auth", "已恢复上次输入")

        active_section = data.get("active_section", "workspace")
        active_tab = data.get("active_tab", "task")
        self.switch_workspace_tab(active_tab if active_tab in self.view.workspace_panels else "task")
        self.switch_section(active_section if active_section in self.view.section_frames else "workspace")

    def on_close(self) -> None:
        self.save_preferences()
        self.root.destroy()

    def clear_queue(self) -> None:
        if not messagebox.askyesno("确认", "确定要清空下载队列吗？"):
            return
        for item in self.view.queue_tree.get_children():
            self.view.queue_tree.delete(item)
        self.download_queue.clear()
        self.view.update_metric("queue", "0 个任务")
        self.log("下载队列已清空")

    def pause_selected(self) -> None:
        selected = self.view.queue_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择要暂停的任务")
            return
        for item in selected:
            values = self.view.queue_tree.item(item, "values")
            if values[1] == "下载中":
                self.view.queue_tree.set(item, "status", "已暂停")
                self.log(f"已暂停任务: {values[0]}")

    def resume_selected(self) -> None:
        selected = self.view.queue_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择要继续的任务")
            return
        for item in selected:
            values = self.view.queue_tree.item(item, "values")
            if values[1] == "已暂停":
                self.view.queue_tree.set(item, "status", "等待中")
                self.log(f"已继续任务: {values[0]}")

    def delete_selected(self) -> None:
        selected = self.view.queue_tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择要删除的任务")
            return
        if not messagebox.askyesno("确认", f"确定要删除选中的 {len(selected)} 个任务吗？"):
            return
        for item in selected:
            values = self.view.queue_tree.item(item, "values")
            self.view.queue_tree.delete(item)
            self.log(f"已删除任务: {values[0]}")

    def show_item_details(self, _event) -> None:
        selected = self.view.queue_tree.selection()
        if not selected:
            return

        item = selected[0]
        values = self.view.queue_tree.item(item, "values")
        detail_window = tk.Toplevel(self.root)
        detail_window.title("任务详情")
        detail_window.geometry("440x320")

        detail_text = tk.Text(detail_window, wrap=tk.WORD)
        detail_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        detail_text.insert(
            tk.END,
            "\n".join(
                (
                    f"文件名: {values[0]}",
                    f"状态: {values[1]}",
                    f"进度: {values[2]}",
                    f"速度: {values[3]}",
                    f"大小: {values[4]}",
                    f"错误信息: {values[5]}",
                )
            ),
        )
        detail_text.configure(state=tk.DISABLED)

    def init_download_queue(self, file_list: list[str]) -> None:
        for item in self.view.queue_tree.get_children():
            self.view.queue_tree.delete(item)
        self.download_queue.clear()

        for filename in file_list:
            self.view.queue_tree.insert("", tk.END, values=(filename, "等待中", "0%", "-", "-", "-"))
            self.download_queue.append(
                {
                    "filename": filename,
                    "status": "等待中",
                    "progress": "0%",
                    "speed": "-",
                    "size": "-",
                    "error": "-",
                }
            )

        self.view.update_metric("queue", f"{len(file_list)} 个任务")
        self.log(f"已初始化下载队列，共 {len(file_list)} 个文件")
        self.switch_section("queue")

    def update_queue_item(
        self,
        filename: str,
        status: str,
        progress: str,
        speed: str,
        size: str = "-",
        error: str = "-",
    ) -> None:
        for item in self.view.queue_tree.get_children():
            values = self.view.queue_tree.item(item, "values")
            if values[0] != filename:
                continue
            self.view.queue_tree.item(item, values=(filename, status, progress, speed, size, error))
            break

    def handle_download_error(self, error_info: dict) -> None:
        filename = error_info.get("filename", "未知文件")
        error_msg = error_info.get("error", "未知错误")
        timestamp = error_info.get("timestamp", "")
        self.update_queue_item(filename, "错误", "0%", "-", "-", error_msg)
        self.log(f"错误 [{timestamp}]: {filename} - {error_msg}")
        self.state.status_var.set(f"下载错误: {filename}")
        self.view.update_metric("status", "存在错误")

    @staticmethod
    def _format_exception_message(exc: Exception, default_message: str) -> str:
        message = str(exc).strip()
        if message and message != "None":
            return message
        if type(exc) is not Exception:
            return f"{default_message}: {type(exc).__name__}"
        return default_message
