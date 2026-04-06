import tempfile
import unittest
from pathlib import Path

from douyin_downloader.api.client import DouyinAPIClient
from douyin_downloader.cookies.manager import CookieManager
from douyin_downloader.gui.persistence import FileLogger, PreferencesStore


class RuntimeSupportTest(unittest.TestCase):
    def test_api_client_disables_environment_proxy(self):
        client = DouyinAPIClient(CookieManager(curl_text='-b "sessionid=test;"'))
        self.assertFalse(client.session.trust_env)
        self.assertEqual(client.session.proxies, {})

    def test_preferences_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gui_state.json"
            store = PreferencesStore(path)
            payload = {"url": "https://example.com", "curl_text": "curl test"}
            store.save(payload)
            self.assertEqual(store.load(), payload)

    def test_file_logger_writes_lines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "log.txt"
            logger = FileLogger(path)
            logger.write("first line")
            logger.write("second line")
            content = path.read_text(encoding="utf-8")
            self.assertIn("first line", content)
            self.assertIn("second line", content)


if __name__ == "__main__":
    unittest.main()
