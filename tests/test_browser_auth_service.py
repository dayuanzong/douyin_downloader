import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from douyin_downloader.services.browser_auth_service import BrowserAuthService, BrowserCandidate


class BrowserAuthServiceTest(unittest.TestCase):
    def test_build_cookie_text_only_keeps_target_cookie_pairs(self):
        cookies = [
            {"name": "ttwid", "value": "abc", "domain": ".douyin.com"},
            {"name": "msToken", "value": "xyz", "domain": "www.iesdouyin.com"},
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

    def test_cookie_text_to_context_cookies_duplicates_domains(self):
        cookies = BrowserAuthService._cookie_text_to_context_cookies("sessionid=abc; ttwid=xyz")
        pairs = {(item["name"], item["domain"]) for item in cookies}
        self.assertEqual(
            pairs,
            {
                ("sessionid", ".douyin.com"),
                ("sessionid", ".iesdouyin.com"),
                ("ttwid", ".douyin.com"),
                ("ttwid", ".iesdouyin.com"),
            },
        )

    def test_looks_authenticated_requires_login_cookie(self):
        self.assertTrue(BrowserAuthService._looks_authenticated("ttwid=abc; sessionid=123"))
        self.assertFalse(BrowserAuthService._looks_authenticated("passport_csrf_token=123"))


if __name__ == "__main__":
    unittest.main()
