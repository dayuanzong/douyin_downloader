from __future__ import annotations

import os
import tkinter as tk
from dataclasses import dataclass


@dataclass
class GUIState:
    author_url_var: tk.StringVar
    aweme_url_var: tk.StringVar
    download_mode_var: tk.StringVar
    save_dir_var: tk.StringVar
    status_var: tk.StringVar
    progress_var: tk.StringVar
    active_section: str = "workspace"
    active_tab: str = "task"
    is_downloading: bool = False

    @classmethod
    def create(cls, root: tk.Misc) -> "GUIState":
        return cls(
            author_url_var=tk.StringVar(master=root),
            aweme_url_var=tk.StringVar(master=root),
            download_mode_var=tk.StringVar(master=root, value="author"),
            save_dir_var=tk.StringVar(master=root, value=os.path.join(os.getcwd(), "downloads")),
            status_var=tk.StringVar(master=root, value="就绪"),
            progress_var=tk.StringVar(master=root, value="等待开始..."),
        )
