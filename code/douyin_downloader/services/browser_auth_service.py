from __future__ import annotations

import base64
import ctypes
import json
import re
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from Cryptodome.Cipher import AES

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional dependency
    PlaywrightError = RuntimeError
    sync_playwright = None


@dataclass(frozen=True, slots=True)
class BrowserCandidate:
    name: str
    executable_path: Path
    user_data_dir: Path


DEFAULT_BROWSER_CANDIDATES = (
    BrowserCandidate(
        "Edge",
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path.home() / "AppData/Local/Microsoft/Edge/User Data",
    ),
    BrowserCandidate(
        "Chrome",
        Path(r"D:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path.home() / "AppData/Local/Google/Chrome/User Data",
    ),
    BrowserCandidate(
        "Chrome",
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path.home() / "AppData/Local/Google/Chrome/User Data",
    ),
)


CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(slots=True)
class BrowserCookieImportResult:
    cookie_text: str
    browser_name: str
    executable_path: Path
    cookie_count: int
    source: str


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


class BrowserAuthService:
    def __init__(
        self,
        preferred_executable: Path | str | None = None,
        browser_candidates: Iterable[BrowserCandidate] | None = None,
    ):
        self.preferred_executable = Path(preferred_executable) if preferred_executable else None
        self.browser_candidates = tuple(browser_candidates or DEFAULT_BROWSER_CANDIDATES)

    def resolve_browser(self) -> BrowserCandidate:
        if self.preferred_executable:
            for candidate in self.browser_candidates:
                if candidate.executable_path == self.preferred_executable and candidate.executable_path.exists():
                    return candidate
            if self.preferred_executable.exists():
                return BrowserCandidate(
                    name=self._label_for_path(self.preferred_executable),
                    executable_path=self.preferred_executable,
                    user_data_dir=self._guess_user_data_dir(self.preferred_executable),
                )

        for candidate in self.browser_candidates:
            if candidate.executable_path.exists():
                return candidate

        raise FileNotFoundError("未找到可用浏览器，请先安装 Edge 或 Chrome，或在代码里配置浏览器路径。")

    def import_cookie_text(
        self,
        target_url: str = "https://www.douyin.com/",
        timeout_seconds: int = 300,
        poll_interval: float = 1.0,
        log_callback=None,
    ) -> BrowserCookieImportResult:
        primary_browser = self.resolve_browser()
        profile_locked = False

        for browser in self._ordered_browsers(primary_browser):
            try:
                profile_result = self._import_from_installed_browser(browser, log_callback=log_callback)
            except PermissionError:
                profile_locked = True
                self._emit_log(log_callback, f"{browser.name} 的 Cookie 数据库正在被占用，已尝试其它浏览器资料。")
                continue
            if profile_result:
                return profile_result

        if profile_locked:
            self._emit_log(log_callback, "检测到浏览器资料被占用；若要直接复用本机登录态，建议先关闭浏览器后再点一次导入。")
        else:
            self._emit_log(log_callback, f"{primary_browser.name} 本地资料中未找到可用抖音 Cookie，转为手动登录导入。")

        return self._import_from_interactive_browser(
            browser=primary_browser,
            target_url=target_url,
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
            log_callback=log_callback,
        )

    def _import_from_installed_browser(self, browser: BrowserCandidate, log_callback=None) -> BrowserCookieImportResult | None:
        if not browser.user_data_dir.exists():
            return None

        best_cookie_text = ""
        best_profile = None
        for profile_dir in self._iter_browser_profiles(browser.user_data_dir):
            cookie_text = self._read_profile_cookie_text(browser.user_data_dir, profile_dir)
            if self._count_cookie_pairs(cookie_text) > self._count_cookie_pairs(best_cookie_text):
                best_cookie_text = cookie_text
                best_profile = profile_dir.name

        cookie_count = self._count_cookie_pairs(best_cookie_text)
        if cookie_count == 0:
            return None

        self._emit_log(log_callback, f"已从 {browser.name} 本地登录资料读取到 {cookie_count} 个 Cookie（配置文件: {best_profile}）。")
        return BrowserCookieImportResult(
            cookie_text=best_cookie_text,
            browser_name=browser.name,
            executable_path=browser.executable_path,
            cookie_count=cookie_count,
            source=f"{browser.name} 本地资料/{best_profile}",
        )

    def _read_profile_cookie_text(self, user_data_dir: Path, profile_dir: Path) -> str:
        cookie_db_path = profile_dir / "Network/Cookies"
        if not cookie_db_path.exists():
            return ""

        master_key = self._read_browser_master_key(user_data_dir / "Local State")
        if not master_key:
            return ""

        with tempfile.TemporaryDirectory() as temp_dir:
            copied_db = Path(temp_dir) / "Cookies"
            shutil.copy2(cookie_db_path, copied_db)

            connection = sqlite3.connect(str(copied_db))
            try:
                cursor = connection.execute(
                    """
                    SELECT host_key, name, value, encrypted_value
                    FROM cookies
                    WHERE host_key LIKE '%douyin.com%'
                    ORDER BY host_key, name
                    """
                )
                rows = cursor.fetchall()
            finally:
                connection.close()

        cookies: list[dict] = []
        for host_key, name, value, encrypted_value in rows:
            decrypted_value = value or self._decrypt_cookie_value(encrypted_value, master_key)
            if not name or not decrypted_value:
                continue
            cookies.append(
                {
                    "name": name,
                    "value": decrypted_value,
                    "domain": host_key,
                }
            )
        return self._build_cookie_text(cookies)

    def _import_from_interactive_browser(
        self,
        browser: BrowserCandidate,
        target_url: str,
        timeout_seconds: int,
        poll_interval: float,
        log_callback=None,
    ) -> BrowserCookieImportResult:
        if sync_playwright is None:
            raise RuntimeError("当前环境未安装 Playwright，无法通过浏览器登录导入 Cookie。")

        self._emit_log(
            log_callback,
            f"正在启动 {browser.name} 登录窗口，请在浏览器中完成抖音登录；登录完成后直接关闭浏览器窗口。",
        )

        best_cookie_text = ""
        best_cookie_count = 0
        with sync_playwright() as playwright:
            instance = playwright.chromium.launch(
                executable_path=str(browser.executable_path),
                headless=False,
            )
            context = instance.new_context()
            page = context.new_page()

            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            except PlaywrightError:
                page.goto(target_url, timeout=60000)

            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                if not instance.is_connected():
                    break

                try:
                    cookies = context.cookies()
                except PlaywrightError:
                    break

                cookie_text = self._build_cookie_text(cookies)
                cookie_count = self._count_cookie_pairs(cookie_text)
                if cookie_count >= best_cookie_count and cookie_text:
                    best_cookie_text = cookie_text
                    best_cookie_count = cookie_count

                time.sleep(poll_interval)

            if instance.is_connected():
                instance.close()

        if not best_cookie_text:
            raise RuntimeError("未能从浏览器读取到抖音 Cookie，请确认已打开并完成登录。")

        self._emit_log(log_callback, f"已从 {browser.name} 登录窗口读取到 {best_cookie_count} 个 Cookie。")
        return BrowserCookieImportResult(
            cookie_text=best_cookie_text,
            browser_name=browser.name,
            executable_path=browser.executable_path,
            cookie_count=best_cookie_count,
            source=f"{browser.name} 登录窗口",
        )

    def _read_browser_master_key(self, local_state_path: Path) -> bytes | None:
        if not local_state_path.exists():
            return None

        state = json.loads(local_state_path.read_text(encoding="utf-8"))
        encrypted_key = state.get("os_crypt", {}).get("encrypted_key")
        if not encrypted_key:
            return None

        key_bytes = base64.b64decode(encrypted_key)
        if key_bytes.startswith(b"DPAPI"):
            key_bytes = key_bytes[5:]
        return self._crypt_unprotect_data(key_bytes)

    def _decrypt_cookie_value(self, encrypted_value: bytes, master_key: bytes) -> str:
        if not encrypted_value:
            return ""

        if encrypted_value.startswith((b"v10", b"v11")):
            nonce = encrypted_value[3:15]
            ciphertext = encrypted_value[15:-16]
            tag = encrypted_value[-16:]
            cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
            return cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8", errors="ignore")

        return self._crypt_unprotect_data(encrypted_value).decode("utf-8", errors="ignore")

    def _crypt_unprotect_data(self, encrypted_bytes: bytes) -> bytes:
        if not encrypted_bytes:
            return b""

        buffer = ctypes.create_string_buffer(encrypted_bytes, len(encrypted_bytes))
        blob_in = DATA_BLOB(len(encrypted_bytes), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        blob_out = DATA_BLOB()
        if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        ):
            raise ctypes.WinError()

        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)

    @staticmethod
    def _iter_browser_profiles(user_data_dir: Path) -> list[Path]:
        profiles = []
        for path in user_data_dir.iterdir():
            if not path.is_dir():
                continue
            if path.name == "Default" or path.name.startswith("Profile "):
                profiles.append(path)
        profiles.sort(key=lambda item: (item.name != "Default", item.name))
        return profiles

    def _ordered_browsers(self, primary_browser: BrowserCandidate) -> list[BrowserCandidate]:
        ordered = [primary_browser]
        seen = {primary_browser.executable_path}
        for candidate in self.browser_candidates:
            if candidate.executable_path in seen:
                continue
            if not candidate.executable_path.exists():
                continue
            seen.add(candidate.executable_path)
            ordered.append(candidate)
        return ordered

    @staticmethod
    def _build_cookie_text(cookies: list[dict]) -> str:
        pairs: list[str] = []
        seen_names: set[str] = set()

        for cookie in cookies:
            name = CONTROL_CHAR_PATTERN.sub("", str(cookie.get("name", ""))).replace("=", "").replace(";", "").strip()
            value = CONTROL_CHAR_PATTERN.sub("", str(cookie.get("value", ""))).replace(";", "").strip()
            domain = str(cookie.get("domain", "")).lower()
            if not name or not value:
                continue
            if "douyin.com" not in domain:
                continue
            if name in seen_names:
                continue
            seen_names.add(name)
            pairs.append(f"{name}={value}")

        return "; ".join(pairs)

    @staticmethod
    def _count_cookie_pairs(cookie_text: str) -> int:
        if not cookie_text.strip():
            return 0
        return sum(1 for segment in cookie_text.split(";") if "=" in segment)

    @staticmethod
    def _label_for_path(executable_path: Path) -> str:
        lower_name = executable_path.name.lower()
        if "edge" in lower_name:
            return "Edge"
        if "chrome" in lower_name:
            return "Chrome"
        return executable_path.stem

    @staticmethod
    def _guess_user_data_dir(executable_path: Path) -> Path:
        lower_path = str(executable_path).lower()
        if "edge" in lower_path:
            return Path.home() / "AppData/Local/Microsoft/Edge/User Data"
        if "chrome" in lower_path:
            return Path.home() / "AppData/Local/Google/Chrome/User Data"
        return Path.home()

    @staticmethod
    def _emit_log(log_callback, message: str) -> None:
        if log_callback:
            log_callback(message)
