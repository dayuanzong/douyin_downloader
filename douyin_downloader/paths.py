from __future__ import annotations

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
CODE_DIR = PROJECT_ROOT
ROOT_DIR = PROJECT_ROOT

DOWNLOADS_DIR = PROJECT_ROOT / "downloads"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
BROWSER_AUTH_DIR = RUNTIME_DIR / "browser_auth"
MANAGED_EDGE_PROFILE_DIR = BROWSER_AUTH_DIR / "edge_profile"
MANAGED_AUTH_COOKIE_FILE = BROWSER_AUTH_DIR / "cookie.txt"

GUI_STATE_FILE = RUNTIME_DIR / "gui_state.json"
LOG_FILE = RUNTIME_DIR / "log.txt"
INPUT_HISTORY_FILE = RUNTIME_DIR / "input_history.txt"

CURL_TEMPLATE_FILE = PROJECT_ROOT / "cURL.txt"
COOKIE_GUIDE_FILE = PROJECT_ROOT / "Cookie获取教程.txt"


def ensure_runtime_dir() -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR
