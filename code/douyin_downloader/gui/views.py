from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from douyin_downloader.gui.state import GUIState


class MainWindowView:
    SIDEBAR_ITEMS = (
        ("workspace", "工作台"),
        ("queue", "下载队列"),
        ("logs", "运行日志"),
        ("future", "扩展预留"),
    )
    TOP_TABS = (
        ("task", "任务配置"),
        ("auth", "认证输入"),
        ("options", "下载选项"),
    )

    def __init__(self, root: tk.Tk, state: GUIState):
        self.root = root
        self.state = state
        self.sidebar_buttons: dict[str, tk.Button] = {}
        self.top_tab_buttons: dict[str, tk.Button] = {}
        self.section_frames: dict[str, tk.Frame] = {}
        self.workspace_panels: dict[str, tk.Frame] = {}
        self.metric_labels: dict[str, ttk.Label] = {}
        self.queue_tree = None
        self.log_text = None
        self.curl_text = None
        self.progress_bar = None
        self.start_button = None
        self.stop_button = None
        self.import_browser_button = None

        self._build()

    def _build(self) -> None:
        self.root.title("抖音下载工作台")
        self.root.geometry("1280x820")
        self.root.minsize(1100, 720)
        self.root.configure(bg="#e8edf5")

        shell = tk.Frame(self.root, bg="#e8edf5")
        shell.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(shell, bg="#0f172a", width=110)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        content = tk.Frame(shell, bg="#e8edf5")
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_sidebar(sidebar)
        self._build_content(content)
        self.show_section("workspace")
        self.show_workspace_panel("task")

    def _build_sidebar(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text="抖音\n下载台",
            justify=tk.CENTER,
            font=("Microsoft YaHei UI", 16, "bold"),
            bg="#0f172a",
            fg="#f8fafc",
            pady=20,
        ).pack(fill=tk.X)

        for section_key, label in self.SIDEBAR_ITEMS:
            button = tk.Button(
                parent,
                text=label,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                font=("Microsoft YaHei UI", 11, "bold"),
                bg="#0f172a",
                fg="#cbd5e1",
                activebackground="#1e293b",
                activeforeground="#ffffff",
                pady=14,
            )
            button.pack(fill=tk.X, padx=10, pady=6)
            self.sidebar_buttons[section_key] = button

    def _build_content(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg="#ffffff", padx=24, pady=18)
        header.pack(fill=tk.X, padx=18, pady=(18, 10))

        tk.Label(
            header,
            text="下载工作台",
            font=("Microsoft YaHei UI", 20, "bold"),
            bg="#ffffff",
            fg="#0f172a",
        ).pack(anchor=tk.W)
        tk.Label(
            header,
            text="先把架构拆清楚，再把视频、图文、认证和后续功能稳定扩展下去。",
            font=("Microsoft YaHei UI", 10),
            bg="#ffffff",
            fg="#475569",
        ).pack(anchor=tk.W, pady=(6, 0))

        metrics = tk.Frame(parent, bg="#e8edf5")
        metrics.pack(fill=tk.X, padx=18, pady=(0, 10))
        for key, title, value in (
            ("status", "当前状态", "就绪"),
            ("queue", "队列概览", "0 个任务"),
            ("auth", "认证输入", "等待输入"),
        ):
            card = tk.Frame(metrics, bg="#ffffff", padx=18, pady=16, highlightthickness=1, highlightbackground="#d7dee9")
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10) if key != "auth" else 0)
            tk.Label(card, text=title, font=("Microsoft YaHei UI", 10), bg="#ffffff", fg="#64748b").pack(anchor=tk.W)
            label = ttk.Label(card, text=value, font=("Microsoft YaHei UI", 13, "bold"))
            label.pack(anchor=tk.W, pady=(8, 0))
            self.metric_labels[key] = label

        top_tabs = tk.Frame(parent, bg="#e8edf5")
        top_tabs.pack(fill=tk.X, padx=18)
        for tab_key, label in self.TOP_TABS:
            button = tk.Button(
                top_tabs,
                text=label,
                relief=tk.FLAT,
                bd=0,
                cursor="hand2",
                font=("Microsoft YaHei UI", 10, "bold"),
                bg="#cfd8e3",
                fg="#334155",
                activebackground="#b9c6d8",
                activeforeground="#0f172a",
                padx=18,
                pady=10,
            )
            button.pack(side=tk.LEFT, padx=(0, 8), pady=(0, 10))
            self.top_tab_buttons[tab_key] = button

        section_host = tk.Frame(parent, bg="#e8edf5")
        section_host.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 12))

        self.section_frames["workspace"] = self._build_workspace_section(section_host)
        self.section_frames["queue"] = self._build_queue_section(section_host)
        self.section_frames["logs"] = self._build_logs_section(section_host)
        self.section_frames["future"] = self._build_future_section(section_host)

        footer = tk.Frame(parent, bg="#ffffff", padx=18, pady=12, highlightthickness=1, highlightbackground="#d7dee9")
        footer.pack(fill=tk.X, padx=18, pady=(0, 18))

        self.progress_bar = ttk.Progressbar(footer, mode="determinate")
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        ttk.Label(footer, textvariable=self.state.progress_var, width=36).pack(side=tk.RIGHT)

        status_bar = tk.Frame(parent, bg="#e8edf5")
        status_bar.pack(fill=tk.X, padx=18, pady=(0, 18))
        ttk.Label(status_bar, textvariable=self.state.status_var).pack(side=tk.LEFT)

    def _build_workspace_section(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg="#e8edf5")
        panel_host = tk.Frame(frame, bg="#e8edf5")
        panel_host.pack(fill=tk.BOTH, expand=True)

        self.workspace_panels["task"] = self._build_task_panel(panel_host)
        self.workspace_panels["auth"] = self._build_auth_panel(panel_host)
        self.workspace_panels["options"] = self._build_options_panel(panel_host)
        return frame

    def _build_task_panel(self, parent: tk.Frame) -> tk.Frame:
        panel = tk.Frame(parent, bg="#ffffff", padx=22, pady=22, highlightthickness=1, highlightbackground="#d7dee9")

        ttk.Label(panel, text="下载入口", font=("Microsoft YaHei UI", 12, "bold")).grid(row=0, column=0, columnspan=3, sticky=tk.W)
        mode_row = tk.Frame(panel, bg="#ffffff")
        mode_row.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(16, 4))
        ttk.Label(mode_row, text="下载模式").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_row, text="作者主页", value="author", variable=self.state.download_mode_var).pack(side=tk.LEFT, padx=(14, 0))
        ttk.Radiobutton(mode_row, text="单作品分享", value="aweme", variable=self.state.download_mode_var).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(panel, text="作者主页 URL").grid(row=2, column=0, sticky=tk.W, pady=8)
        ttk.Entry(panel, textvariable=self.state.author_url_var).grid(
            row=2, column=1, columnspan=2, sticky=tk.EW, pady=8, padx=(12, 0)
        )

        ttk.Label(panel, text="作品分享口令 / 短链 / 作品链接").grid(row=3, column=0, sticky=tk.W, pady=8)
        ttk.Entry(panel, textvariable=self.state.aweme_url_var).grid(
            row=3, column=1, columnspan=2, sticky=tk.EW, pady=8, padx=(12, 0)
        )

        ttk.Label(panel, text="保存目录").grid(row=4, column=0, sticky=tk.W, pady=8)
        ttk.Entry(panel, textvariable=self.state.save_dir_var).grid(row=4, column=1, sticky=tk.EW, pady=8, padx=(12, 8))
        self.browse_dir_button = ttk.Button(panel, text="浏览")
        self.browse_dir_button.grid(row=4, column=2, sticky=tk.EW, pady=8)

        tips = tk.Frame(panel, bg="#f8fafc", padx=14, pady=14, highlightthickness=1, highlightbackground="#e2e8f0")
        tips.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=(16, 18))
        tk.Label(
            tips,
            text=(
                "作者主页模式用于批量下载该作者作品。"
                "单作品分享模式请粘贴抖音分享口令、短链或作品页链接，不要直接使用浏览器里带登录态的地址。"
                "如果作品需要更高权限再补充 Cookie / cURL；程序会优先尝试作品可用的最高质量媒体地址。"
            ),
            bg="#f8fafc",
            fg="#475569",
            font=("Microsoft YaHei UI", 10),
            anchor="w",
            justify=tk.LEFT,
            wraplength=760,
        ).pack(fill=tk.X)

        actions = tk.Frame(panel, bg="#ffffff")
        actions.grid(row=6, column=0, columnspan=3, sticky=tk.EW)
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        self.start_button = tk.Button(
            actions,
            text="开始下载",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#0f9d58",
            fg="#ffffff",
            activebackground="#0b7d46",
            activeforeground="#ffffff",
            pady=12,
        )
        self.start_button.grid(row=0, column=0, sticky=tk.EW, padx=(0, 8))

        self.stop_button = tk.Button(
            actions,
            text="停止任务",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#d92d20",
            fg="#ffffff",
            activebackground="#b42318",
            activeforeground="#ffffff",
            pady=12,
            state=tk.DISABLED,
        )
        self.stop_button.grid(row=0, column=1, sticky=tk.EW, padx=(8, 0))

        panel.columnconfigure(1, weight=1)
        return panel

    def _build_auth_panel(self, parent: tk.Frame) -> tk.Frame:
        panel = tk.Frame(parent, bg="#ffffff", padx=22, pady=22, highlightthickness=1, highlightbackground="#d7dee9")

        ttk.Label(panel, text="认证输入", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(
            panel,
            text="支持粘贴完整 cURL，或只粘贴 Cookie 字符串。若只粘贴 Cookie，请在任务配置里填写作者主页 URL 或作品分享链接。",
        ).pack(anchor=tk.W, pady=(8, 14))

        toolbar = tk.Frame(panel, bg="#ffffff")
        toolbar.pack(fill=tk.X, pady=(0, 10))
        self.import_browser_button = ttk.Button(toolbar, text="浏览器登录导入")
        self.import_browser_button.pack(side=tk.LEFT)
        self.import_curl_button = ttk.Button(toolbar, text="从文件导入")
        self.import_curl_button.pack(side=tk.LEFT, padx=(8, 0))
        self.clear_curl_button = ttk.Button(toolbar, text="清空输入")
        self.clear_curl_button.pack(side=tk.LEFT, padx=(8, 0))

        self.curl_text = tk.Text(
            panel,
            wrap=tk.WORD,
            height=18,
            font=("Consolas", 10),
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            relief=tk.FLAT,
            padx=12,
            pady=12,
        )
        self.curl_text.pack(fill=tk.BOTH, expand=True)

        hint = tk.Frame(panel, bg="#f8fafc", padx=14, pady=12, highlightthickness=1, highlightbackground="#e2e8f0")
        hint.pack(fill=tk.X, pady=(12, 0))
        tk.Label(
            hint,
            text="推荐输入方式：1. 直接点“浏览器登录导入”，程序会优先读取你本机 Edge/Chrome 已登录资料；只有读不到时才会退回手动登录窗口。2. 粘贴完整 cURL。3. 只粘贴 Cookie 字符串。",
            bg="#f8fafc",
            fg="#475569",
            font=("Microsoft YaHei UI", 10),
            anchor="w",
        ).pack(fill=tk.X)
        return panel

    def _build_options_panel(self, parent: tk.Frame) -> tk.Frame:
        panel = tk.Frame(parent, bg="#ffffff", padx=22, pady=22, highlightthickness=1, highlightbackground="#d7dee9")
        ttk.Label(panel, text="下载选项", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor=tk.W)

        options_card = tk.Frame(panel, bg="#f8fafc", padx=18, pady=18, highlightthickness=1, highlightbackground="#e2e8f0")
        options_card.pack(fill=tk.X, pady=(14, 0))
        tk.Label(
            options_card,
            text="这里先预留给后续的下载质量、并发、过滤规则和命名策略。",
            bg="#f8fafc",
            fg="#475569",
            font=("Microsoft YaHei UI", 10),
            anchor="w",
            justify=tk.LEFT,
        ).pack(fill=tk.X)
        return panel

    def _build_queue_section(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg="#ffffff", padx=18, pady=18, highlightthickness=1, highlightbackground="#d7dee9")

        controls = tk.Frame(frame, bg="#ffffff")
        controls.pack(fill=tk.X, pady=(0, 10))
        self.clear_queue_button = ttk.Button(controls, text="清空队列")
        self.clear_queue_button.pack(side=tk.LEFT)
        self.pause_button = ttk.Button(controls, text="暂停选中")
        self.pause_button.pack(side=tk.LEFT, padx=(8, 0))
        self.resume_button = ttk.Button(controls, text="继续选中")
        self.resume_button.pack(side=tk.LEFT, padx=(8, 0))
        self.delete_button = ttk.Button(controls, text="删除选中")
        self.delete_button.pack(side=tk.LEFT, padx=(8, 0))

        columns = ("filename", "status", "progress", "speed", "size", "error")
        self.queue_tree = ttk.Treeview(frame, columns=columns, show="headings")
        for name, label, width in (
            ("filename", "文件名", 280),
            ("status", "状态", 100),
            ("progress", "进度", 90),
            ("speed", "速度", 110),
            ("size", "大小", 100),
            ("error", "错误信息", 260),
        ):
            self.queue_tree.heading(name, text=label)
            self.queue_tree.column(name, width=width, anchor=tk.W)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.queue_tree.yview)
        self.queue_tree.configure(yscrollcommand=scrollbar.set)
        self.queue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        return frame

    def _build_logs_section(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg="#ffffff", padx=18, pady=18, highlightthickness=1, highlightbackground="#d7dee9")
        self.log_text = tk.Text(
            frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#ffffff",
            fg="#0f172a",
            relief=tk.FLAT,
            padx=10,
            pady=10,
        )
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        return frame

    def _build_future_section(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg="#ffffff", padx=18, pady=18, highlightthickness=1, highlightbackground="#d7dee9")
        tk.Label(
            frame,
            text="扩展预留区",
            bg="#ffffff",
            fg="#0f172a",
            font=("Microsoft YaHei UI", 14, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            frame,
            text="后续如果要加入账号管理、批量任务、素材过滤或配置中心，这里可以继续扩展，不需要再把主界面全部打散重写。",
            bg="#ffffff",
            fg="#475569",
            font=("Microsoft YaHei UI", 10),
            justify=tk.LEFT,
            anchor="w",
            wraplength=760,
        ).pack(anchor=tk.W, pady=(12, 0))
        return frame

    def show_section(self, section_key: str) -> None:
        for key, frame in self.section_frames.items():
            if key == section_key:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()

        for key, button in self.sidebar_buttons.items():
            button.configure(
                bg="#1e293b" if key == section_key else "#0f172a",
                fg="#ffffff" if key == section_key else "#cbd5e1",
            )

    def show_workspace_panel(self, panel_key: str) -> None:
        for key, frame in self.workspace_panels.items():
            if key == panel_key:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()

        for key, button in self.top_tab_buttons.items():
            button.configure(
                bg="#0f172a" if key == panel_key else "#cfd8e3",
                fg="#ffffff" if key == panel_key else "#334155",
            )

    def append_log(self, message: str) -> None:
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def clear_logs(self) -> None:
        self.log_text.delete("1.0", tk.END)

    def get_curl_text(self) -> str:
        return self.curl_text.get("1.0", tk.END).strip()

    def set_curl_text(self, value: str) -> None:
        self.curl_text.delete("1.0", tk.END)
        self.curl_text.insert("1.0", value)

    def update_metric(self, key: str, value: str) -> None:
        label = self.metric_labels.get(key)
        if label:
            label.configure(text=value)
