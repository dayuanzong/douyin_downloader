import unittest
from pathlib import Path
import shutil
from douyin_downloader.downloader.downloader import Downloader
from douyin_downloader.utils.sec_user_id_extractor import extract_sec_user_id
from douyin_downloader.cookies.manager import CookieManager
from douyin_downloader.api.client import DouyinAPIClient

class PostFetcherTest(unittest.TestCase):
    def setUp(self):
        """
        设置测试所需的环境。
        """
        self.curl_file = Path('samples/cURL.txt')
        self.save_dir = Path('test_downloads')
        self.save_dir.mkdir(exist_ok=True)
        cookie_manager = CookieManager(self.curl_file)
        api_client = DouyinAPIClient(cookie_manager)
        self.downloader = Downloader(api_client, self.save_dir)

    def test_get_all_posts_count(self):
        """
        测试是否能正确获取所有作品的数量。
        """
        user_url = "https://www.douyin.com/user/MS4wLjABAAAA6Z1DuHTs9hc2Mx9-UcG0b5eWqxPj68-J3w3hNFadbhw?from_tab_name=main&vid=7557333739286662427"
        sec_user_id = extract_sec_user_id(user_url)
        self.assertIsNotNone(sec_user_id, "未能从 URL 中提取 sec_user_id")

        total_posts = 0
        max_cursor = 0
        while True:
            data = self.downloader.api_client.get_user_posts(sec_user_id, max_cursor)
            self.assertIsNotNone(data, "API 请求失败，返回 None")
            
            aweme_list = data.get('aweme_list', [])
            total_posts += len(aweme_list)

            if not data.get('has_more'):
                break
            max_cursor = data.get('max_cursor', 0)

        print(f"获取到的作品总数: {total_posts}")
        self.assertGreater(total_posts, 0, "未能获取到任何作品")

    def test_download_single_video(self):
        """
        测试是否能成功下载单个视频。
        """
        user_url = "https://www.douyin.com/user/MS4wLjABAAAA6Z1DuHTs9hc2Mx9-UcG0b5eWqxPj68-J3w3hNFadbhw?from_tab_name=main&vid=7557333739286662427"
        sec_user_id = extract_sec_user_id(user_url)
        self.assertIsNotNone(sec_user_id, "未能从 URL 中提取 sec_user_id")

        data = self.downloader.api_client.get_user_posts(sec_user_id, 0)
        self.assertIsNotNone(data, "API 请求失败，返回 None")
        aweme_list = data.get('aweme_list', [])
        self.assertGreater(len(aweme_list), 0, "未能获取到任何作品")

        first_item = aweme_list[0]
        print("视频数据详情:", first_item.get('video'))
        self.downloader._download_item(first_item)

        video_id = first_item['aweme_id']
        desc = first_item.get('desc', 'no_desc')
        valid_desc = "".join(c for c in desc if c.isalnum() or c in (' ', '_')).rstrip()
        expected_filename = f"{valid_desc}_{video_id}.mp4"
        expected_filepath = self.save_dir / expected_filename

        self.assertTrue(expected_filepath.exists(), f"下载的文件不存在: {expected_filepath}")
        print(f"文件已成功下载到: {expected_filepath.resolve()}")

    def tearDown(self):
        """
        清理测试后创建的文件和目录。
        """
        pass # 暂时禁用清理，以便检查下载的文件
        # if self.save_dir.exists():
        #     shutil.rmtree(self.save_dir)

if __name__ == '__main__':
    unittest.main()