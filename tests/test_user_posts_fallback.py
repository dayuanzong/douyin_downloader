import unittest

from douyin_downloader.api.client import DouyinAPIClient
from douyin_downloader.cookies.manager import CookieManager


class UserPostsFallbackTest(unittest.TestCase):
    def test_get_user_posts_uses_browser_when_legacy_request_fails(self):
        class FallbackClient(DouyinAPIClient):
            def __init__(self):
                super().__init__(CookieManager(curl_text="sessionid=test; ttwid=test"))
                self.browser_calls = []

            def _request_json(self, *args, **kwargs):
                self._set_error("empty response", kind="api")
                return None

            def _get_browser_user_posts(self, sec_user_id: str, *, max_cursor: int = 0):
                self.browser_calls.append((sec_user_id, max_cursor))
                return {
                    "status_code": 0,
                    "has_more": 0,
                    "aweme_list": [{"aweme_id": "123"}],
                }

        client = FallbackClient()
        data = client.get_user_posts("sec-user", 0)

        self.assertEqual(client.browser_calls, [("sec-user", 0)])
        self.assertEqual(data["aweme_list"][0]["aweme_id"], "123")

    def test_headers_and_signer_use_same_edge_version(self):
        client = DouyinAPIClient(CookieManager(curl_text="sessionid=test; ttwid=test"))
        headers = client._get_headers()

        self.assertIn(f"Chrome/{client.browser_major_version}.0.0.0", client.user_agent)
        self.assertIn(f"Edg/{client.browser_major_version}.0.0.0", headers["user-agent"])
        self.assertIn(f'v="{client.browser_major_version}"', headers["sec-ch-ua"])

    def test_build_edge_user_agent(self):
        user_agent = DouyinAPIClient._build_edge_user_agent(136)
        self.assertIn("Chrome/136.0.0.0", user_agent)
        self.assertIn("Edg/136.0.0.0", user_agent)


if __name__ == "__main__":
    unittest.main()
