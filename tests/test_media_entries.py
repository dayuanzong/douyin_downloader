import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from douyin_downloader.downloader.downloader import Downloader


class DummyClient:
    def _get_headers(self):
        return {}


class MediaEntriesTest(unittest.TestCase):
    def setUp(self):
        self.downloader = Downloader(DummyClient(), Path("downloads"))

    def test_build_video_entry(self):
        item = {
            "aweme_id": "123",
            "desc": "video sample",
            "video": {
                "play_addr_h264": {
                    "url_list": ["https://example.com/video_1080p.mp4"],
                }
            },
        }
        entries = self.downloader.build_media_entries(item)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["filename"], "video sample_123.mp4")

    def test_build_video_entry_prefers_highest_bitrate_urls(self):
        item = {
            "aweme_id": "321",
            "desc": "video quality sample",
            "video": {
                "bit_rate": [
                    {
                        "bit_rate": 1_500_000,
                        "gear_name": "normal_540",
                        "play_addr": {
                            "url_list": ["https://example.com/video_540.mp4"],
                            "width": 960,
                            "height": 540,
                        },
                    },
                    {
                        "bit_rate": 4_500_000,
                        "gear_name": "adapt_1080_1",
                        "play_addr": {
                            "url_list": ["https://example.com/video_1080.mp4"],
                            "width": 1920,
                            "height": 1080,
                        },
                    },
                ],
                "play_addr": {"url_list": ["https://example.com/video_fallback.mp4"]},
            },
        }
        entries = self.downloader.build_media_entries(item)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["url"], "https://example.com/video_1080.mp4")
        self.assertEqual(entries[0]["candidate_urls"][0], "https://example.com/video_1080.mp4")

    def test_build_image_entries_from_images(self):
        item = {
            "aweme_id": "456",
            "desc": "image sample",
            "images": [
                {"url_list": ["https://example.com/a.webp"]},
                {"url_list": ["https://example.com/b.jpg"]},
            ],
        }
        entries = self.downloader.build_media_entries(item)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["filename"], "image sample_456_01.webp")
        self.assertEqual(entries[1]["filename"], "image sample_456_02.jpg")
        self.assertGreaterEqual(len(entries[0]["candidate_urls"]), 1)

    def test_build_motion_entries_from_image_post_info(self):
        item = {
            "aweme_id": "789",
            "desc": "motion sample",
            "image_post_info": {
                "images": [
                    {
                        "display_image": {"url_list": ["https://example.com/cover.jpg"]},
                        "live_photo_video": {"url_list": ["https://example.com/live.mp4"]},
                    }
                ]
            },
        }
        entries = self.downloader.build_media_entries(item)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["filename"], "motion sample_789_01.jpg")
        self.assertEqual(entries[1]["filename"], "motion sample_789_01_motion.mp4")

    def test_image_post_with_video_prefers_images(self):
        item = {
            "aweme_id": "999",
            "aweme_type": 68,
            "desc": "gallery sample",
            "video": {
                "play_addr_h264": {
                    "url_list": ["https://example.com/video_1080p.mp4"],
                }
            },
            "images": [
                {
                    "url_list": ["https://example.com/1.webp"],
                    "download_url_list": ["https://example.com/1-watermark.webp"],
                },
                {
                    "url_list": ["https://example.com/2.jpg"],
                    "download_url_list": ["https://example.com/2-watermark.jpg"],
                },
            ],
        }
        entries = self.downloader.build_media_entries(item)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["type"], "image")
        self.assertEqual(entries[0]["url"], "https://example.com/1.webp")
        self.assertEqual(entries[1]["url"], "https://example.com/2.jpg")
        self.assertEqual(
            entries[0]["candidate_urls"],
            [
                "https://example.com/1.webp",
                "https://example.com/1-watermark.webp",
            ],
        )

    def test_duplicate_image_nodes_are_deduplicated(self):
        shared = {"url_list": ["https://example.com/a.webp"]}
        item = {
            "aweme_id": "111",
            "desc": "duplicate sample",
            "images": [shared],
            "image_post_info": {"images": [shared]},
        }
        entries = self.downloader.build_media_entries(item)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["filename"], "duplicate sample_111_01.webp")

    def test_export_failed_entries_creates_reports(self):
        with TemporaryDirectory() as temp_dir:
            downloader = Downloader(DummyClient(), Path(temp_dir))
            downloader.failed_entries = [
                {
                    "filename": "sample_01.webp",
                    "type": "image",
                    "media_id": "123",
                    "description": "sample",
                    "url": "https://example.com/a.webp",
                    "candidate_urls": ["https://example.com/a.webp", "https://example.com/a.jpeg"],
                    "error": "403 Forbidden",
                }
            ]
            json_path, text_path = downloader.export_failed_entries()
            self.assertTrue(json_path.exists())
            self.assertTrue(text_path.exists())
            self.assertIn("sample_01.webp", text_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
