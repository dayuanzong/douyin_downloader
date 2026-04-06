import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from douyin_downloader.services.browser_auth_service import BrowserAuthService, BrowserCandidate


class BrowserAuthServiceTest(unittest.TestCase):
    def test_build_cookie_text_only_keeps_douyin_cookie_pairs(self):
        cookies = [
            {"name": "ttwid", "value": "abc", "domain": ".douyin.com"},
            {"name": "msToken", "value": "xyz", "domain": "www.douyin.com"},
            {"name": "sid", "value": "ignore", "domain": ".example.com"},
            {"name": "ttwid", "value": "duplicate", "domain": ".douyin.com"},
        ]
        cookie_text = BrowserAuthService._build_cookie_text(cookies)
        self.assertEqual(cookie_text, "ttwid=abc; msToken=xyz")

    def test_build_cookie_text_strips_invalid_cookie_characters(self):
        cookies = [
            {"name": "SEARCH_RESULT_LIST_TYPE", "value": "\x14\x1d15", "domain": ".douyin.com"},
            {"name": "msToken", "value": "abc\r\n", "domain": ".douyin.com"},
        ]
        cookie_text = BrowserAuthService._build_cookie_text(cookies)
        self.assertEqual(cookie_text, "SEARCH_RESULT_LIST_TYPE=15; msToken=abc")

    def test_resolve_browser_prefers_existing_preferred_path(self):
        with TemporaryDirectory() as temp_dir:
            preferred = Path(temp_dir) / "msedge.exe"
            preferred.touch()
            user_data_dir = Path(temp_dir) / "EdgeUserData"
            user_data_dir.mkdir()
            service = BrowserAuthService(
                preferred_executable=preferred,
                browser_candidates=(
                    BrowserCandidate("Fallback", Path(temp_dir) / "missing.exe", Path(temp_dir) / "FallbackData"),
                ),
            )
            candidate = service.resolve_browser()
            self.assertEqual(candidate.name, "Edge")
            self.assertEqual(candidate.executable_path, preferred)

    def test_iter_browser_profiles_prioritizes_default(self):
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            (base / "Profile 2").mkdir()
            (base / "Default").mkdir()
            (base / "Profile 1").mkdir()
            profiles = BrowserAuthService._iter_browser_profiles(base)
            self.assertEqual([profile.name for profile in profiles], ["Default", "Profile 1", "Profile 2"])


if __name__ == "__main__":
    unittest.main()
