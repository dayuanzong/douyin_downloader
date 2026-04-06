import unittest

from douyin_downloader.cookies.manager import CookieManager
from douyin_downloader.cookies.parser import (
    extract_author_url_from_curl,
    extract_cookie_from_curl,
    extract_sec_user_id_from_curl,
)


class CurlParserTest(unittest.TestCase):
    def setUp(self):
        self.curl_text = """curl "https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id=MS4wLjABAAAA_TEST_USER" ^
  -H "accept: application/json" ^
  -b ^"sessionid=test-session; ttwid=test-ttwid;^" ^
  -H "referer: https://www.douyin.com/user/MS4wLjABAAAA_TEST_USER?from_tab_name=main"
"""

    def test_extract_cookie_from_inline_curl(self):
        cookie = extract_cookie_from_curl(self.curl_text)
        self.assertEqual(cookie, "sessionid=test-session; ttwid=test-ttwid;")

    def test_extract_identity_from_inline_curl(self):
        self.assertEqual(extract_sec_user_id_from_curl(self.curl_text), "MS4wLjABAAAA_TEST_USER")
        self.assertEqual(
            extract_author_url_from_curl(self.curl_text),
            "https://www.douyin.com/user/MS4wLjABAAAA_TEST_USER?from_tab_name=main",
        )

    def test_cookie_manager_supports_direct_text(self):
        manager = CookieManager(curl_text=self.curl_text)
        self.assertEqual(manager.get_cookie(), "sessionid=test-session; ttwid=test-ttwid")

    def test_extract_plain_cookie_text(self):
        plain_cookie = "sessionid=test-session; ttwid=test-ttwid;"
        self.assertEqual(extract_cookie_from_curl(plain_cookie), plain_cookie)

    def test_cookie_manager_sanitizes_control_characters(self):
        manager = CookieManager(curl_text="sessionid=test-session; SEARCH_RESULT_LIST_TYPE=\x14\x1d15; msToken=xyz\r\n")
        self.assertEqual(manager.get_cookie(), "sessionid=test-session; SEARCH_RESULT_LIST_TYPE=15; msToken=xyz")


if __name__ == "__main__":
    unittest.main()
