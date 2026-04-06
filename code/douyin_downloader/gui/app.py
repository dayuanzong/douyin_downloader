from __future__ import annotations

import tkinter as tk

from douyin_downloader.gui.controller import MainWindowController
from douyin_downloader.gui.state import GUIState
from douyin_downloader.gui.views import MainWindowView
from douyin_downloader.services.download_service import DownloadService


def build_app(root: tk.Tk | None = None) -> MainWindowController:
    root = root or tk.Tk()
    state = GUIState.create(root)
    view = MainWindowView(root, state)
    service = DownloadService()
    return MainWindowController(root, state, view, service)


def main() -> None:
    controller = build_app()
    controller.root.mainloop()
