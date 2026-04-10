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

from douyin_downloader.cookies.parser import extract_cookie_from_curl
from douyin_downloader.paths import MANAGED_AUTH_COOKIE_FILE, MANAGED_EDGE_PROFILE_DIR, ensure_runtime_dir

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional dependency
    PlaywrightError = RuntimeError
    sync_playwright = None


TARGET_DOMAINS = ("douyin.com", "iesdouyin.com")
COOKIE_REQUIRED_NAMES = ("sessionid", "sid_tt", "uid_tt", "ttwid")
COOKIE_CONTEXT_NAMES = (
    "msToken",
    "passport_csrf_token",
    "sid_guard",
    "sessionid_ss",
    "uid_tt_ss",
    "sid_ucp_v1",
    "ssid_ucp_v1",
)


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
        managed_user_data_dir: Path | str | None = None,
    ):
        self.preferred_executable = Path(preferred_executable) if preferred_executable else None
        self.browser_candidates = tuple(browser_candidates or DEFAULT_BROWSER_CANDIDATES)
        self.managed_user_data_dir = Path(managed_user_data_dir) if managed_user_data_dir else MANAGED_EDGE_PROFILE_DIR

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

        raise FileNotFoundError("No supported browser executable was found.")

    def import_cookie_text(
        self,
        target_url: str = "https://www.douyin.com/",
        timeout_seconds: int = 300,
        poll_interval: float = 1.0,
        bootstrap_cookie_text: str | None = None,
        log_callback=None,
    ) -> BrowserCookieImportResult:
        browser = self.resolve_browser()

        bootstrap_cookie_text = (bootstrap_cookie_text or "").strip()
        if bootstrap_cookie_text:
            normalized_cookie_text = self._normalize_cookie_text_input(bootstrap_cookie_text)
            if normalized_cookie_text:
                self._write_cached_cookie_text(normalized_cookie_text)
                try:
                    self._seed_managed_profile_from_cookie_text(
                        browser,
                        normalized_cookie_text,
                        target_url=target_url,
                        log_callback=log_callback,
                    )
                    managed_result = self._import_from_managed_profile(browser, target_url=target_url, log_callback=log_callback)
                    if managed_result:
                        return managed_result
                except Exception as exc:
                    self._emit_log(log_callback, f"Managed browser bootstrap skipped: {exc}")
                return self._result_from_cookie_text(browser, normalized_cookie_text, source="provided authentication text")

        managed_result = self._import_from_managed_profile(browser, target_url=target_url, log_callback=log_callback)
        if managed_result:
            return managed_result

        cached_result = self._import_from_cached_cookie_store(browser, log_callback=log_callback)
        if cached_result:
            return cached_result

        installed_result = self._import_from_installed_browser(browser, log_callback=log_callback)
        if installed_result:
            self._write_cached_cookie_text(installed_result.cookie_text)
            try:
                self._seed_managed_profile_from_cookie_text(
                    browser,
                    installed_result.cookie_text,
                    target_url=target_url,
                    log_callback=log_callback,
                )
                managed_result = self._import_from_managed_profile(browser, target_url=target_url, log_callback=log_callback)
                if managed_result:
                    return managed_result
            except Exception as exc:
                self._emit_log(log_callback, f"Managed browser bootstrap skipped: {exc}")
            return installed_result

        cached_result = self._import_from_cached_cookie_store(browser, log_callback=log_callback)
        if cached_result:
            return cached_result

        return self._import_from_interactive_browser(
            browser=browser,
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
        profile_locked = False

        for profile_dir in self._iter_browser_profiles(browser.user_data_dir):
            try:
                cookie_text = self._read_profile_cookie_text(browser.user_data_dir, profile_dir)
            except PermissionError:
                profile_locked = True
                self._emit_log(log_callback, f"Browser profile is locked: {profile_dir.name}")
                continue

            if self._count_cookie_pairs(cookie_text) > self._count_cookie_pairs(best_cookie_text):
                best_cookie_text = cookie_text
                best_profile = profile_dir.name

        cookie_count = self._count_cookie_pairs(best_cookie_text)
        if cookie_count == 0:
            if profile_locked:
                self._emit_log(log_callback, "Installed browser cookies are locked by the running browser.")
            return None

        self._emit_log(log_callback, f"Loaded {cookie_count} cookies from {browser.name}/{best_profile}.")
        return BrowserCookieImportResult(
            cookie_text=best_cookie_text,
            browser_name=browser.name,
            executable_path=browser.executable_path,
            cookie_count=cookie_count,
            source=f"{browser.name} local profile/{best_profile}",
        )

    def _import_from_managed_profile(
        self,
        browser: BrowserCandidate,
        *,
        target_url: str,
        log_callback=None,
    ) -> BrowserCookieImportResult | None:
        if sync_playwright is None:
            return None

        managed_dir = self._managed_profile_dir(browser)
        if not managed_dir.exists():
            return None

        try:
            cookies = self._load_cookies_from_persistent_profile(browser, managed_dir, target_url=target_url)
        except Exception as exc:
            self._emit_log(log_callback, f"Managed browser profile is not ready: {exc}")
            return None
        cookie_text = self._build_cookie_text(cookies)
        cookie_count = self._count_cookie_pairs(cookie_text)
        if cookie_count == 0 or not self._is_rich_authenticated_cookie_text(cookie_text):
            return None

        self._emit_log(log_callback, f"Loaded {cookie_count} cookies from managed {browser.name} profile.")
        return BrowserCookieImportResult(
            cookie_text=cookie_text,
            browser_name=browser.name,
            executable_path=browser.executable_path,
            cookie_count=cookie_count,
            source=f"managed {browser.name} profile",
        )

    def _seed_managed_profile_from_cookie_text(
        self,
        browser: BrowserCandidate,
        cookie_text: str,
        *,
        target_url: str,
        log_callback=None,
    ) -> None:
        if sync_playwright is None:
            raise RuntimeError("Playwright is required to bootstrap the managed browser profile.")

        managed_dir = self._managed_profile_dir(browser)
        ensure_runtime_dir()
        managed_dir.mkdir(parents=True, exist_ok=True)

        cookies = self._cookie_text_to_context_cookies(cookie_text)
        if not cookies:
            raise RuntimeError("No valid cookies were found in the provided authentication text.")

        self._emit_log(log_callback, f"Bootstrapping managed {browser.name} profile with {len(cookies)} cookies.")
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(user_data_dir=str(managed_dir), headless=True)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                context.add_cookies(cookies)
                try:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                except PlaywrightError:
                    pass
                try:
                    page.wait_for_timeout(1200)
                except PlaywrightError:
                    pass
            finally:
                context.close()

    def _import_from_interactive_browser(
        self,
        browser: BrowserCandidate,
        target_url: str,
        timeout_seconds: int,
        poll_interval: float,
        log_callback=None,
    ) -> BrowserCookieImportResult:
        if sync_playwright is None:
            raise RuntimeError("Playwright is required for interactive browser sign-in.")

        managed_dir = self._managed_profile_dir(browser)
        ensure_runtime_dir()
        managed_dir.mkdir(parents=True, exist_ok=True)

        self._emit_log(log_callback, f"Opening managed {browser.name} profile for manual sign-in.")
        best_cookie_text = ""
        best_cookie_count = 0

        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(managed_dir),
                executable_path=str(browser.executable_path),
                headless=False,
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                try:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                except PlaywrightError:
                    pass

                deadline = time.monotonic() + timeout_seconds
                while time.monotonic() < deadline:
                    cookie_text = self._build_cookie_text(context.cookies("https://www.douyin.com/"))
                    cookie_count = self._count_cookie_pairs(cookie_text)
                    if cookie_count >= best_cookie_count and self._looks_authenticated(cookie_text):
                        best_cookie_text = cookie_text
                        best_cookie_count = cookie_count
                    time.sleep(poll_interval)
            finally:
                context.close()

        if not best_cookie_text:
            raise RuntimeError("No usable Douyin login cookies were collected from the browser.")

        self._write_cached_cookie_text(best_cookie_text)
        self._emit_log(log_callback, f"Collected {best_cookie_count} cookies from interactive sign-in.")
        return BrowserCookieImportResult(
            cookie_text=best_cookie_text,
            browser_name=browser.name,
            executable_path=browser.executable_path,
            cookie_count=best_cookie_count,
            source=f"interactive {browser.name} profile",
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
                    WHERE host_key LIKE '%douyin.com%' OR host_key LIKE '%iesdouyin.com%'
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
            cookies.append({"name": name, "value": decrypted_value, "domain": host_key})
        return self._build_cookie_text(cookies)

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

    def _load_cookies_from_persistent_profile(
        self,
        browser: BrowserCandidate,
        managed_dir: Path,
        *,
        target_url: str,
    ) -> list[dict]:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(user_data_dir=str(managed_dir), headless=True)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                try:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                except PlaywrightError:
                    page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(800)

                cookies = []
                for url in ("https://www.douyin.com/", "https://www.iesdouyin.com/"):
                    try:
                        cookies.extend(context.cookies(url))
                    except PlaywrightError:
                        continue
                return cookies
            finally:
                context.close()

    def _managed_profile_dir(self, browser: BrowserCandidate) -> Path:
        browser_key = browser.name.lower().replace(" ", "_")
        return self.managed_user_data_dir.parent / browser_key if self.managed_user_data_dir.name == "edge_profile" else self.managed_user_data_dir

    def _import_from_cached_cookie_store(self, browser: BrowserCandidate, log_callback=None) -> BrowserCookieImportResult | None:
        cookie_text = self._read_cached_cookie_text()
        if not self._looks_authenticated(cookie_text):
            return None
        if not self._is_rich_authenticated_cookie_text(cookie_text):
            self._emit_log(
                log_callback,
                f"Ignoring weak local auth cache with {self._count_cookie_pairs(cookie_text)} cookies.",
            )
            self._clear_cached_cookie_text()
            return None
        self._emit_log(log_callback, f"Loaded {self._count_cookie_pairs(cookie_text)} cookies from the local auth cache.")
        return self._result_from_cookie_text(browser, cookie_text, source="local auth cache")

    @staticmethod
    def _normalize_cookie_text_input(cookie_text: str) -> str:
        normalized = extract_cookie_from_curl(cookie_text) or cookie_text.strip()
        pairs: list[str] = []
        seen_names: set[str] = set()
        for segment in normalized.split(";"):
            if "=" not in segment:
                continue
            name, value = segment.split("=", 1)
            clean_name = CONTROL_CHAR_PATTERN.sub("", name).replace("=", "").replace(";", "").strip()
            clean_value = CONTROL_CHAR_PATTERN.sub("", value).replace(";", "").strip()
            if not clean_name or not clean_value or clean_name in seen_names:
                continue
            seen_names.add(clean_name)
            pairs.append(f"{clean_name}={clean_value}")
        return "; ".join(pairs)

    @staticmethod
    def _result_from_cookie_text(browser: BrowserCandidate, cookie_text: str, *, source: str) -> BrowserCookieImportResult:
        return BrowserCookieImportResult(
            cookie_text=cookie_text,
            browser_name=browser.name,
            executable_path=browser.executable_path,
            cookie_count=BrowserAuthService._count_cookie_pairs(cookie_text),
            source=source,
        )

    def _read_cached_cookie_text(self) -> str:
        try:
            return MANAGED_AUTH_COOKIE_FILE.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return ""

    def _write_cached_cookie_text(self, cookie_text: str) -> None:
        ensure_runtime_dir()
        MANAGED_AUTH_COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        MANAGED_AUTH_COOKIE_FILE.write_text(cookie_text, encoding="utf-8")

    def _clear_cached_cookie_text(self) -> None:
        try:
            MANAGED_AUTH_COOKIE_FILE.unlink()
        except FileNotFoundError:
            return

    @staticmethod
    def _cookie_text_to_context_cookies(cookie_text: str) -> list[dict]:
        cookies: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for segment in cookie_text.split(";"):
            if "=" not in segment:
                continue
            name, value = segment.split("=", 1)
            clean_name = CONTROL_CHAR_PATTERN.sub("", name).replace("=", "").replace(";", "").strip()
            clean_value = CONTROL_CHAR_PATTERN.sub("", value).replace(";", "").strip()
            if not clean_name or not clean_value:
                continue
            for domain in (".douyin.com", ".iesdouyin.com"):
                key = (clean_name, domain)
                if key in seen:
                    continue
                seen.add(key)
                cookies.append(
                    {
                        "name": clean_name,
                        "value": clean_value,
                        "domain": domain,
                        "path": "/",
                        "secure": True,
                    }
                )
        return cookies

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
            if not any(target in domain for target in TARGET_DOMAINS):
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
    def _looks_authenticated(cookie_text: str) -> bool:
        if not cookie_text:
            return False
        return any(f"{name}=" in cookie_text for name in COOKIE_REQUIRED_NAMES)

    @staticmethod
    def _is_rich_authenticated_cookie_text(cookie_text: str) -> bool:
        if not BrowserAuthService._looks_authenticated(cookie_text):
            return False
        cookie_count = BrowserAuthService._count_cookie_pairs(cookie_text)
        if cookie_count >= 8:
            return True
        context_hits = sum(1 for name in COOKIE_CONTEXT_NAMES if f"{name}=" in cookie_text)
        return context_hits >= 2

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
