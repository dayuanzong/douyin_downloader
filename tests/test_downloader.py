import asyncio
import unittest
from pathlib import Path

from douyin_downloader.api.client import DouyinAPIClient
from douyin_downloader.cookies.manager import CookieManager
from douyin_downloader.downloader.downloader import Downloader
from douyin_downloader.paths import CURL_TEMPLATE_FILE
from douyin_downloader.utils.sec_user_id_extractor import extract_sec_user_id


class PostFetcherTest(unittest.TestCase):
    def setUp(self):
        self.curl_file = CURL_TEMPLATE_FILE
        if not self.curl_file.exists():
            self.skipTest("本地未配置 cURL.txt，跳过联网集成测试。")

        curl_text = self.curl_file.read_text(encoding="utf-8").strip()
        if not curl_text or "在这里粘贴" in curl_text:
            self.skipTest("cURL.txt 仍是模板内容，跳过联网集成测试。")

        self.save_dir = Path.cwd() / "downloads"
        self.save_dir.mkdir(exist_ok=True)
        cookie_manager = CookieManager(curl_file=self.curl_file)
        api_client = DouyinAPIClient(cookie_manager)
        self.downloader = Downloader(api_client, self.save_dir)

    def test_get_all_posts_count(self):
        user_url = (
            "https://www.douyin.com/user/"
            "MS4wLjABAAAA6Z1DuHTs9hc2Mx9-UcG0b5eWqxPj68-J3w3hNFadbhw"
            "?from_tab_name=main&vid=7557333739286662427"
        )
        sec_user_id = extract_sec_user_id(user_url)
        self.assertIsNotNone(sec_user_id, "未能从 URL 中提取 sec_user_id")

        total_posts = 0
        max_cursor = 0
        while True:
            data = self.downloader.api_client.get_user_posts(sec_user_id, max_cursor)
            self.assertIsNotNone(data, "API 请求失败，返回 None")

            aweme_list = data.get("aweme_list", [])
            total_posts += len(aweme_list)

            if not data.get("has_more"):
                break
            max_cursor = data.get("max_cursor", 0)

        self.assertGreater(total_posts, 0, "未能获取到任何作品")

    def test_download_single_video(self):
        user_url = (
            "https://www.douyin.com/user/"
            "MS4wLjABAAAA6Z1DuHTs9hc2Mx9-UcG0b5eWqxPj68-J3w3hNFadbhw"
            "?from_tab_name=main&vid=7557333739286662427"
        )
        sec_user_id = extract_sec_user_id(user_url)
        self.assertIsNotNone(sec_user_id, "未能从 URL 中提取 sec_user_id")

        data = self.downloader.api_client.get_user_posts(sec_user_id, 0)
        self.assertIsNotNone(data, "API 请求失败，返回 None")
        aweme_list = data.get("aweme_list", [])
        self.assertGreater(len(aweme_list), 0, "未能获取到任何作品")

        first_item = aweme_list[0]
        asyncio.run(self.downloader._download_item(first_item))

        video_id = first_item["aweme_id"]
        desc = first_item.get("desc", "no_desc")
        valid_desc = "".join(c for c in desc if c.isalnum() or c in (" ", "_")).strip() or "no_desc"
        expected_filepath = self.save_dir / f"{valid_desc}_{video_id}.mp4"
        self.assertTrue(expected_filepath.exists(), f"下载的文件不存在: {expected_filepath}")


if __name__ == "__main__":
    unittest.main()
