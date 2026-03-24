
import requests
from requests.exceptions import JSONDecodeError
from douyin_downloader.cookies.manager import CookieManager
from douyin_downloader.utils.xbogus import generate_x_bogus

class DouyinAPIClient:
    """
    一个用于与抖音 API 交互的客户端。
    """

    def __init__(self, cookie_manager: CookieManager, error_callback=None):
        """
        初始化 DouyinAPIClient。

        :param cookie_manager: Cookie 管理器实例。
        :param error_callback: 错误回调函数，用于处理错误信息。
        """
        self.cookie_manager = cookie_manager
        self.session = requests.Session()
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        self.error_callback = error_callback

    def _get_headers(self) -> dict:
        """
        构建请求头。

        :return: 包含必要请求头的字典。
        """
        return {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'priority': 'u=1, i',
            'referer': 'https://www.douyin.com/',
            'sec-ch-ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0',
            'Cookie': self.cookie_manager.get_cookie() or 'ttwid=1%7CZ6MKbdL_Kj8xKRwSvvjvUiDb5-FNznsFV5MiBzYOCUU%7C1762648371%7C1de9cecc994a65aa7a1158b5ae70072bf553beb847b95660f043d78093974a62'
        }

    def get_user_posts(self, sec_user_id: str, max_cursor: int = 0) -> dict | None:
        """
        获取指定用户的作品列表。

        :param sec_user_id: 用户的 sec_user_id。
        :param max_cursor: 分页游标。
        :return: API 响应的 JSON 数据，如果请求失败则返回 None。
        """
        params = {
            'device_platform': 'webapp',
            'aid': '6383',
            'channel': 'channel_pc_web',
            'sec_user_id': sec_user_id,
            'max_cursor': max_cursor,
            'locate_item_id': '7557333739286662427',
            'locate_query': 'false',
            'show_live_replay_strategy': '1',
            'need_time_list': '1',
            'time_list_query': '0',
            'whale_cut_token': '',
            'cut_version': '1',
            'count': '18',
            'publish_video_strategy_type': '2',
            'from_user_page': '1',
            'update_version_code': '170400',
            'pc_client_type': '1',
            'pc_libra_divert': 'Windows',
            'support_h265': '1',
            'support_dash': '1',
            'cpu_core_num': '8',
            'version_code': '290100',
            'version_name': '29.1.0',
            'cookie_enabled': 'true',
            'screen_width': '1536',
            'screen_height': '864',
            'browser_language': 'zh-CN',
            'browser_platform': 'Win32',
            'browser_name': 'Edge',
            'browser_version': '142.0.0.0',
            'browser_online': 'true',
            'engine_name': 'Blink',
            'engine_version': '142.0.0.0',
            'os_name': 'Windows',
            'os_version': '10',
            'device_memory': '8',
            'platform': 'PC',
            'downlink': '10',
            'effective_type': '4g',
            'round_trip_time': '200',
            'webid': '7569420535352804914',
        }
        base_url = "https://www.douyin.com/aweme/v1/web/aweme/post/"
        
        # The xbogus signature generation is complex and might need a separate library or a deeper implementation.
        # For now, we will try without it, as sometimes it is not strictly required.
        # If the request fails, we will need to investigate how to generate a valid xbogus signature.
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{base_url}?{query_string}"
        signed_url, _, _ = generate_x_bogus(full_url, self.user_agent)
        
        try:
            response = self.session.get(signed_url, headers=self._get_headers(), timeout=10)
            response.raise_for_status()
            return response.json()
        except JSONDecodeError:
            error_msg = f"JSON 解码失败。服务器响应: {response.text[:200]}..."
            if self.error_callback:
                self.error_callback(error_msg)
            else:
                print(error_msg)
            return None
        except requests.RequestException as e:
            error_msg = f"请求 API 时出错: {e}"
            if self.error_callback:
                self.error_callback(error_msg)
            else:
                print(error_msg)
            return None
        except Exception as e:
            error_msg = f"处理响应时出错: {e}"
            if self.error_callback:
                self.error_callback(error_msg)
            else:
                print(error_msg)
            return None


