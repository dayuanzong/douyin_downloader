import unittest
from pathlib import Path

from douyin_downloader.models import DownloadRequest
from douyin_downloader.services.download_service import DownloadService
from douyin_downloader.utils.aweme_extractor import extract_aweme_id, extract_share_url


class FakeAPIClient:
    def __init__(self, resolved_url: str):
        self.resolved_url = resolved_url
        self.last_error = None
        self.last_error_kind = None

    def resolve_url(self, _url: str) -> str:
        return self.resolved_url


class TargetResolutionTest(unittest.TestCase):
    def setUp(self):
        self.service = DownloadService()

    def test_extract_share_url_from_share_text(self):
        share_text = "这是分享内容 https://v.douyin.com/AbCdEf12/ 复制此链接，打开抖音搜索，直接观看视频！"
        self.assertEqual(extract_share_url(share_text), "https://v.douyin.com/AbCdEf12/")

    def test_extract_share_url_from_real_style_share_text(self):
        share_text = (
            "0.25 g@O.Xm 12/27 RKj:/ 我常感叹人与人之间的关系竟如枯叶般易碎。"
            "# 走着走着就散了  https://v.douyin.com/wRjGIEOxh9w/ 复制此链接，打开Dou音搜索，直接观看视频！"
        )
        self.assertEqual(extract_share_url(share_text), "https://v.douyin.com/wRjGIEOxh9w/")

    def test_extract_aweme_id_from_video_url(self):
        url = "https://www.douyin.com/video/1234567890123456789"
        self.assertEqual(extract_aweme_id(url), "1234567890123456789")

    def test_extract_aweme_id_from_note_url(self):
        url = "https://www.douyin.com/note/9876543210987654321"
        self.assertEqual(extract_aweme_id(url), "9876543210987654321")

    def test_extract_aweme_id_from_modal_query(self):
        url = "https://www.douyin.com/user/MS4wLjABAAAA_TEST?modal_id=7654321098765432109"
        self.assertEqual(extract_aweme_id(url), "7654321098765432109")

    def test_resolve_target_for_video_url(self):
        request = DownloadRequest(url="https://www.douyin.com/video/1234567890123456789", save_dir=Path("downloads"))
        target = self.service.resolve_target(request)
        self.assertEqual(target.kind, "aweme")
        self.assertEqual(target.identifier, "1234567890123456789")

    def test_resolve_target_for_author_url(self):
        request = DownloadRequest(
            url="https://www.douyin.com/user/MS4wLjABAAAA_TEST_USER?from_tab_name=main&vid=7557333739286662427",
            save_dir=Path("downloads"),
        )
        target = self.service.resolve_target(request)
        self.assertEqual(target.kind, "user")
        self.assertEqual(target.identifier, "MS4wLjABAAAA_TEST_USER")

    def test_resolve_target_from_short_link_redirect(self):
        request = DownloadRequest(
            url="https://v.douyin.com/AbCdEf12/",
            save_dir=Path("downloads"),
        )
        target = self.service.resolve_target(
            request,
            api_client=FakeAPIClient("https://www.douyin.com/video/1234567890123456789"),
        )
        self.assertEqual(target.kind, "aweme")
        self.assertEqual(target.identifier, "1234567890123456789")
        self.assertEqual(target.resolved_url, "https://www.douyin.com/video/1234567890123456789")

    def test_resolve_target_raises_network_error_when_short_link_cannot_be_resolved(self):
        request = DownloadRequest(
            url="https://v.douyin.com/AbCdEf12/",
            save_dir=Path("downloads"),
        )
        client = FakeAPIClient("https://v.douyin.com/AbCdEf12/")
        client.last_error = "网络超时，无法解析分享链接，请稍后重试"
        client.last_error_kind = "network"

        with self.assertRaises(RuntimeError) as context:
            self.service.resolve_target(request, api_client=client)

        self.assertIn("网络超时", str(context.exception))


if __name__ == "__main__":
    unittest.main()
