import unittest
from pathlib import Path

from douyin_downloader.models import DownloadRequest
from douyin_downloader.services.browser_auth_service import BrowserCookieImportResult
from douyin_downloader.services.download_service import DownloadService


class StubBrowserAuthService:
    def __init__(self):
        self.calls = []

    def import_cookie_text(self, **kwargs):
        self.calls.append(kwargs)
        bootstrap_cookie_text = kwargs.get("bootstrap_cookie_text")
        cookie_text = "sessionid=managed; ttwid=managed"
        if bootstrap_cookie_text:
            cookie_text = "sessionid=seeded; ttwid=seeded"
        return BrowserCookieImportResult(
            cookie_text=cookie_text,
            browser_name="Edge",
            executable_path=Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            cookie_count=2,
            source="stub",
        )


class DownloadServiceAuthTest(unittest.TestCase):
    def test_build_cookie_manager_bootstraps_managed_profile_from_inline_text(self):
        auth_service = StubBrowserAuthService()
        service = DownloadService(browser_auth_service=auth_service)
        request = DownloadRequest(url="https://www.douyin.com/video/1", curl_text='-b "sessionid=inline; ttwid=inline"')

        cookie_manager = service._build_cookie_manager(request)

        self.assertEqual(cookie_manager.get_cookie(), "sessionid=seeded; ttwid=seeded")
        self.assertEqual(auth_service.calls[0]["bootstrap_cookie_text"], '-b "sessionid=inline; ttwid=inline"')

    def test_build_cookie_manager_uses_managed_profile_without_manual_text(self):
        auth_service = StubBrowserAuthService()
        service = DownloadService(browser_auth_service=auth_service)
        request = DownloadRequest(url="https://www.douyin.com/video/1")

        cookie_manager = service._build_cookie_manager(request)

        self.assertEqual(cookie_manager.get_cookie(), "sessionid=managed; ttwid=managed")
        self.assertNotIn("bootstrap_cookie_text", auth_service.calls[0])


if __name__ == "__main__":
    unittest.main()
