import json
import unittest
from pathlib import Path
from urllib.parse import quote

from douyin_downloader.api.client import DouyinAPIClient
from douyin_downloader.cookies.manager import CookieManager
from douyin_downloader.downloader.downloader import Downloader


class RenderedAwemeDetailTest(unittest.TestCase):
    def setUp(self):
        self.client = DouyinAPIClient(CookieManager(curl_text="ttwid=test"))
        self.downloader = Downloader(self.client, Path("downloads"))

    def test_extract_aweme_detail_from_react_payload(self):
        raw_detail = {
            "awemeId": "1234567890123456789",
            "awemeType": 68,
            "desc": "\u8d70\u7740\u8d70\u7740\u5c31\u6563\u4e86",
            "authorInfo": {"uid": "42", "secUid": "sec_42", "nickname": "tester"},
            "images": [{"urlList": ["https://example.com/1.webp"]}],
        }
        payload = "7:" + json.dumps(
            ["$", "$L9", None, {"awemeId": raw_detail["awemeId"], "aweme": {"statusCode": 0, "detail": raw_detail}}],
            ensure_ascii=False,
        )
        escaped_payload = payload.replace("\\", "\\\\").replace('"', '\\"')
        html = f'<script nonce="" crossorigin="anonymous">self.__pace_f.push([1,"{escaped_payload}"])</script>'

        detail = DouyinAPIClient._extract_aweme_detail_from_page_content(html, raw_detail["awemeId"])
        self.assertIsNotNone(detail)
        self.assertEqual(detail["awemeId"], raw_detail["awemeId"])
        self.assertEqual(detail["desc"], raw_detail["desc"])

    def test_extract_aweme_detail_from_urlencoded_render_payload(self):
        raw_detail = {
            "awemeId": "7626464319467323849",
            "awemeType": 0,
            "desc": "#test video",
            "authorInfo": {"uid": "42", "secUid": "sec_42", "nickname": "tester"},
            "video": {"playAddr": [{"src": "https://example.com/video.mp4"}]},
        }
        payload = quote(json.dumps({"app": {"videoDetail": raw_detail}}, ensure_ascii=False), safe="")
        escaped_payload = payload.replace("\\", "\\\\").replace('"', '\\"')
        html = f'<script nonce="" crossorigin="anonymous">self.__pace_f.push([1,"{escaped_payload}"])</script>'

        detail = DouyinAPIClient._extract_aweme_detail_from_page_content(html, raw_detail["awemeId"])
        self.assertIsNotNone(detail)
        self.assertEqual(detail["awemeId"], raw_detail["awemeId"])
        self.assertEqual(detail["desc"], raw_detail["desc"])

    def test_detect_unavailable_aweme_page_message(self):
        html = "<html><body><h1>作品不存在</h1><p>你访问的内容不存在</p></body></html>"
        message = DouyinAPIClient._detect_unavailable_aweme_page(html, "7626464319467323849")
        self.assertIsNotNone(message)
        self.assertIn("作品不存在", message)

    def test_normalized_rendered_note_supports_images_and_motion(self):
        raw_detail = {
            "awemeId": "123",
            "awemeType": 68,
            "desc": "\u6211\u5e38\u611f\u53f9\u4eba\u4e0e\u4eba\u4e4b\u95f4\u7684\u5173\u7cfb\u7ade\u5982\u67af\u53f6\u822c\u6613\u788e",
            "authorInfo": {"uid": "42", "secUid": "sec_42", "nickname": "tester"},
            "images": [
                {
                    "urlList": ["https://example.com/1.webp"],
                    "downloadUrlList": ["https://example.com/1-watermark.webp"],
                    "video": {"playAddr": [{"src": "https://example.com/1-motion.mp4"}]},
                },
                {
                    "urlList": ["https://example.com/2.jpg"],
                },
            ],
        }

        normalized = DouyinAPIClient._normalize_rendered_aweme_detail(raw_detail)
        entries = self.downloader.build_media_entries(normalized)

        self.assertEqual(normalized["author"]["sec_uid"], "sec_42")
        self.assertEqual(normalized["desc"], raw_detail["desc"])
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["url"], "https://example.com/1.webp")
        self.assertEqual(entries[1]["url"], "https://example.com/1-motion.mp4")
        self.assertEqual(entries[2]["url"], "https://example.com/2.jpg")

    def test_normalized_rendered_video_prefers_highest_quality(self):
        raw_detail = {
            "awemeId": "456",
            "awemeType": 4,
            "desc": "video sample",
            "authorInfo": {"uid": "88", "secUid": "sec_88", "nickname": "tester"},
            "video": {
                "playAddr": [{"src": "https://example.com/fallback.mp4"}],
                "bitRateList": [
                    {
                        "bitRate": 1_000_000,
                        "gearName": "normal_540_0",
                        "width": 960,
                        "height": 540,
                        "playAddr": [{"src": "https://example.com/540.mp4"}],
                    },
                    {
                        "bitRate": 4_000_000,
                        "gearName": "adapt_1080_0",
                        "width": 1920,
                        "height": 1080,
                        "playAddr": [{"src": "https://example.com/1080.mp4"}],
                    },
                ],
            },
        }

        normalized = DouyinAPIClient._normalize_rendered_aweme_detail(raw_detail)
        entries = self.downloader.build_media_entries(normalized)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["url"], "https://example.com/1080.mp4")

    def test_repair_mojibake_text_restores_utf8_chinese(self):
        broken = "\u00e6\u0088\u0091\u00e5\u00b8\u00b8\u00e6\u0084\u009f\u00e5\u008f\u00b9"
        self.assertEqual(DouyinAPIClient._repair_mojibake_text(broken), "\u6211\u5e38\u611f\u53f9")

    def test_candidate_work_urls_prefers_resolved_page_url(self):
        urls = DouyinAPIClient._candidate_work_urls(
            "1234567890123456789",
            "https://www.douyin.com/note/1234567890123456789?previous_page=web_code_link",
        )
        self.assertEqual(
            urls,
            ["https://www.douyin.com/note/1234567890123456789?previous_page=web_code_link"],
        )

    def test_build_browser_video_detail_from_page_state(self):
        detail = DouyinAPIClient._build_browser_video_detail(
            {
                "awemeId": "7619633445971847552",
                "title": "洞这么空，万万没想到#斗米虫 #砍虫 - 抖音",
                "currentSrc": "https://v5-dy-o-abtest.zjcdn.com/example/video.mp4?__vid=7619633445971847552",
                "bitrate": 2017483,
            }
        )
        self.assertIsNotNone(detail)
        self.assertEqual(detail["aweme_id"], "7619633445971847552")
        self.assertEqual(detail["desc"], "洞这么空，万万没想到#斗米虫 #砍虫")
        self.assertEqual(detail["video"]["play_addr"]["url_list"][0], "https://v5-dy-o-abtest.zjcdn.com/example/video.mp4?__vid=7619633445971847552")
        self.assertEqual(detail["video"]["bit_rate"][0]["bit_rate"], 2017483)

    def test_build_browser_video_detail_ignores_placeholder_video(self):
        detail = DouyinAPIClient._build_browser_video_detail(
            {
                "awemeId": "7619633445971847552",
                "title": "placeholder - 抖音",
                "currentSrc": "https://lf-douyin-pc-web.douyinstatic.com/obj/douyin-pc-web/uuu_265.mp4",
                "bitrate": 0,
            }
        )
        self.assertIsNone(detail)

    def test_get_aweme_detail_prefers_network_error_message(self):
        class FailingClient(DouyinAPIClient):
            def _get_web_aweme_detail(self, aweme_id: str, *, page_url: str | None = None):
                self._set_error("\u63a5\u53e3\u8fd4\u56de\u5f02\u5e38", kind="api")
                return None

            def _get_iteminfo_aweme_detail(self, aweme_id: str, *, page_url: str | None = None):
                self._set_error("\u7f51\u7edc\u8d85\u65f6\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u540e\u91cd\u8bd5", kind="network")
                return None

            def _get_rendered_aweme_detail(self, aweme_id: str, *, page_url: str | None = None):
                self._set_error("\u7f51\u7edc\u8d85\u65f6\uff0c\u4f5c\u54c1\u9875\u9762\u52a0\u8f7d\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5", kind="network")
                return None

        client = FailingClient(CookieManager(curl_text="ttwid=test"))
        detail = client.get_aweme_detail(
            "1234567890123456789",
            page_url="https://www.douyin.com/video/1234567890123456789",
        )
        self.assertIsNone(detail)
        self.assertEqual(client.last_error_kind, "network")
        self.assertIn("\u7f51\u7edc\u8d85\u65f6", client.last_error)

    def test_get_aweme_detail_stops_after_rendered_network_failure_with_page_url(self):
        class EarlyExitClient(DouyinAPIClient):
            def __init__(self, cookie_manager):
                super().__init__(cookie_manager)
                self.calls: list[str] = []

            def _get_rendered_aweme_detail(self, aweme_id: str, *, page_url: str | None = None):
                self.calls.append("rendered")
                self._set_error("\u7f51\u7edc\u8d85\u65f6", kind="network")
                return None

            def _get_web_aweme_detail(self, aweme_id: str, *, page_url: str | None = None):
                self.calls.append("web")
                return None

            def _get_iteminfo_aweme_detail(self, aweme_id: str, *, page_url: str | None = None):
                self.calls.append("iteminfo")
                return None

        client = EarlyExitClient(CookieManager(curl_text="ttwid=test"))
        detail = client.get_aweme_detail(
            "1234567890123456789",
            page_url="https://www.douyin.com/note/1234567890123456789",
        )
        self.assertIsNone(detail)
        self.assertEqual(client.calls, ["rendered"])
        self.assertEqual(client.last_error_kind, "network")


if __name__ == "__main__":
    unittest.main()
