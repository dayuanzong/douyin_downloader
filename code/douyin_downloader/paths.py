from __future__ import annotations

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
CODE_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = CODE_DIR.parent

DOWNLOADS_DIR = PROJECT_ROOT / "downloads"
RUNTIME_DIR = CODE_DIR / "runtime"

GUI_STATE_FILE = RUNTIME_DIR / "gui_state.json"
LOG_FILE = RUNTIME_DIR / "log.txt"
INPUT_HISTORY_FILE = RUNTIME_DIR / "input_history.txt"

CURL_TEMPLATE_FILE = CODE_DIR / "cURL.txt"
COOKIE_GUIDE_FILE = CODE_DIR / "Cookie获取教程.txt"


def ensure_runtime_dir() -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR
