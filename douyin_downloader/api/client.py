from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import unquote
from urllib.parse import urlencode
from urllib.parse import urlparse

import requests
from requests.exceptions import JSONDecodeError

from douyin_downloader.cookies.manager import CookieManager
from douyin_downloader.utils.xbogus import generate_x_bogus

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional dependency
    PlaywrightError = RuntimeError
    sync_playwright = None


PACE_F_SCRIPT_PATTERN = re.compile(r'self\.__pace_f\.push\(\[1,"(.*?)"\]\)</script>', re.DOTALL)
DEFAULT_EDGE_PATH = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


class DouyinAPIClient:
    def __init__(self, cookie_manager: CookieManager, error_callback=None):
        self.cookie_manager = cookie_manager
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.proxies.clear()
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.error_callback = error_callback
        self.last_error: str | None = None
        self.last_error_kind: str | None = None

    def _get_headers(self) -> dict:
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "priority": "u=1, i",
            "referer": "https://www.douyin.com/",
            "sec-ch-ua": '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"
            ),
            "Cookie": self.cookie_manager.get_cookie()
            or "ttwid=1%7CZ6MKbdL_Kj8xKRwSvvjvUiDb5-FNznsFV5MiBzYOCUU%7C1762648371%7C1de9cecc994a65aa7a1158b5ae70072bf553beb847b95660f043d78093974a62",
        }

    def _build_context_cookies(self) -> list[dict]:
        cookie_text = self.cookie_manager.get_cookie() or ""
        cookies: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for segment in cookie_text.split(";"):
            if "=" not in segment:
                continue
            name, value = segment.split("=", 1)
            clean_name = name.strip()
            clean_value = value.strip()
            if not clean_name or not clean_value:
                continue
            for domain in (".douyin.com", ".iesdouyin.com"):
                key = (clean_name, domain)
                if key in seen:
                    continue
                seen.add(key)
                cookies.append(
                    {
                        "name": clean_name,
                        "value": clean_value,
                        "domain": domain,
                        "path": "/",
                        "secure": True,
                    }
                )
        return cookies

    def _add_auth_cookies_to_context(self, context) -> None:
        cookies = self._build_context_cookies()
        if not cookies:
            return
        try:
            context.add_cookies(cookies)
        except PlaywrightError:
            return

    def resolve_url(self, url: str) -> str:
        if not url.strip():
            return url

        request_error = None
        response = None
        try:
            response = self.session.get(
                url.strip(),
                headers=self._get_headers(),
                timeout=3,
                allow_redirects=True,
                stream=True,
            )
            resolved_url = response.url or url
            if resolved_url != url:
                self._clear_error()
                return resolved_url
        except requests.Timeout as exc:
            request_error = f"网络超时，无法解析分享链接，请稍后重试: {exc}"
        except requests.RequestException as exc:
            request_error = f"网络错误，无法解析分享链接，请检查网络后重试: {exc}"
        finally:
            if response is not None:
                response.close()

        if self._looks_like_short_douyin_url(url):
            browser_resolved_url = self._resolve_url_with_browser(url)
            if browser_resolved_url:
                self._clear_error()
                return browser_resolved_url

        if request_error:
            self._set_error(request_error, kind="network")
        return url

    def get_user_posts(self, sec_user_id: str, max_cursor: int = 0) -> dict | None:
        params = {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "sec_user_id": sec_user_id,
            "max_cursor": max_cursor,
            "locate_item_id": "7557333739286662427",
            "locate_query": "false",
            "show_live_replay_strategy": "1",
            "need_time_list": "1",
            "time_list_query": "0",
            "whale_cut_token": "",
            "cut_version": "1",
            "count": "18",
            "publish_video_strategy_type": "2",
            "from_user_page": "1",
            "update_version_code": "170400",
            "pc_client_type": "1",
            "pc_libra_divert": "Windows",
            "support_h265": "1",
            "support_dash": "1",
            "cpu_core_num": "8",
            "version_code": "290100",
            "version_name": "29.1.0",
            "cookie_enabled": "true",
            "screen_width": "1536",
            "screen_height": "864",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Edge",
            "browser_version": "142.0.0.0",
            "browser_online": "true",
            "engine_name": "Blink",
            "engine_version": "142.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "device_memory": "8",
            "platform": "PC",
            "downlink": "10",
            "effective_type": "4g",
            "round_trip_time": "200",
            "webid": "7569420535352804914",
        }
        return self._request_json(
            "https://www.douyin.com/aweme/v1/web/aweme/post/",
            params=params,
            sign=True,
            timeout_seconds=10,
            max_attempts=3,
        )

    def get_aweme_detail(self, aweme_id: str, page_url: str | None = None) -> dict | None:
        collected_errors: list[tuple[str, str]] = []
        getters = self._detail_getters(page_url)
        has_page_url_hint = isinstance(page_url, str) and bool(page_url.strip())
        for getter in getters:
            detail = getter(aweme_id, page_url=page_url)
            if detail:
                return detail
            if self.last_error:
                collected_errors.append((self.last_error_kind or "unknown", self.last_error))
            if (
                has_page_url_hint
                and getter.__name__ == "_get_rendered_aweme_detail"
                and self.last_error_kind == "network"
            ):
                break

        network_errors = [message for kind, message in collected_errors if kind == "network"]
        if network_errors:
            self._set_error(network_errors[-1], kind="network")
        elif not self.last_error:
            self._set_error(f"未能获取作品 {aweme_id} 的详情信息", kind="api")
        self._emit_error(self.last_error or "未能获取作品详情")
        return None

    def _detail_getters(self, page_url: str | None):
        if isinstance(page_url, str) and ("/note/" in page_url or "/video/" in page_url):
            return (
                self._get_page_aweme_detail,
                self._get_rendered_aweme_detail,
                self._get_web_aweme_detail,
                self._get_iteminfo_aweme_detail,
            )
        return (
            self._get_web_aweme_detail,
            self._get_iteminfo_aweme_detail,
            self._get_page_aweme_detail,
            self._get_rendered_aweme_detail,
        )

    def _get_web_aweme_detail(self, aweme_id: str, *, page_url: str | None = None) -> dict | None:
        params = {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "aweme_id": aweme_id,
            "pc_client_type": "1",
            "pc_libra_divert": "Windows",
            "support_h265": "1",
            "support_dash": "1",
            "cpu_core_num": "8",
            "version_code": "290100",
            "version_name": "29.1.0",
            "cookie_enabled": "true",
            "screen_width": "1536",
            "screen_height": "864",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Edge",
            "browser_version": "142.0.0.0",
            "browser_online": "true",
            "engine_name": "Blink",
            "engine_version": "142.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "device_memory": "8",
            "platform": "PC",
            "downlink": "10",
            "effective_type": "4g",
            "round_trip_time": "200",
            "webid": "7569420535352804914",
        }
        data = self._request_json(
            "https://www.douyin.com/aweme/v1/web/aweme/detail/",
            params=params,
            sign=True,
            referer=f"https://www.douyin.com/video/{aweme_id}",
            emit_error=False,
            timeout_seconds=4,
            max_attempts=1,
        )
        return self._extract_aweme_detail(data)

    def _get_iteminfo_aweme_detail(self, aweme_id: str, *, page_url: str | None = None) -> dict | None:
        data = self._request_json(
            "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/",
            params={"item_ids": aweme_id},
            referer=f"https://www.iesdouyin.com/share/video/{aweme_id}/",
            emit_error=False,
            timeout_seconds=4,
            max_attempts=1,
        )
        if not isinstance(data, dict):
            return None

        item_list = data.get("item_list")
        if isinstance(item_list, list) and item_list:
            first_item = item_list[0]
            if isinstance(first_item, dict):
                return first_item
        return self._extract_aweme_detail(data)

    def _get_rendered_aweme_detail(self, aweme_id: str, *, page_url: str | None = None) -> dict | None:
        if sync_playwright is None:
            return None

        launch_kwargs = {"headless": True}
        if DEFAULT_EDGE_PATH.exists():
            launch_kwargs["executable_path"] = str(DEFAULT_EDGE_PATH)

        last_playwright_error = None
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(**launch_kwargs)
                try:
                    context = browser.new_context(
                        user_agent=self._get_headers()["user-agent"],
                        locale="zh-CN",
                    )
                    self._add_auth_cookies_to_context(context)
                    for work_url in self._candidate_work_urls(aweme_id, page_url):
                        page = context.new_page()
                        navigation_timeout = 10000 if "/video/" in work_url else 6000
                        try:
                            try:
                                page.goto(work_url, wait_until="commit", timeout=navigation_timeout)
                            except PlaywrightError:
                                page.goto(work_url, timeout=navigation_timeout)

                            for wait_ms in (300, 700, 1200, 2000, 3000):
                                page.wait_for_timeout(wait_ms)
                                try:
                                    page_content = page.content()
                                except PlaywrightError:
                                    page_content = ""
                                detail = self._extract_aweme_detail_from_page_content(page_content, aweme_id)
                                if detail:
                                    self._clear_error()
                                    return self._normalize_rendered_aweme_detail(detail)

                                browser_video_detail = self._extract_browser_video_detail(page, aweme_id)
                                if browser_video_detail:
                                    self._clear_error()
                                    return browser_video_detail

                            if "/video/" in work_url:
                                browser_video_detail = self._wait_for_browser_video_detail(page, aweme_id)
                                if browser_video_detail:
                                    self._clear_error()
                                    return browser_video_detail
                        except PlaywrightError as exc:
                            last_playwright_error = exc
                        finally:
                            page.close()
                finally:
                    browser.close()
        except Exception as exc:
            last_playwright_error = exc

        if last_playwright_error is not None:
            self._set_error(f"网络超时，作品页面加载失败，请稍后重试: {last_playwright_error}", kind="network")
        return None

    def _get_page_aweme_detail(self, aweme_id: str, *, page_url: str | None = None) -> dict | None:
        last_error_message = None
        for work_url in self._candidate_work_urls(aweme_id, page_url):
            response = None
            try:
                headers = self._get_headers()
                headers["accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                headers["referer"] = work_url
                response = self.session.get(work_url, headers=headers, timeout=8)
                response.raise_for_status()
                page_content = response.text
                detail = self._extract_aweme_detail_from_page_content(page_content, aweme_id)
                if detail:
                    self._clear_error()
                    return self._normalize_rendered_aweme_detail(detail)
                missing_message = self._detect_unavailable_aweme_page(page_content, aweme_id)
                if missing_message:
                    self._set_error(missing_message, kind="api")
                    return None
            except requests.Timeout as exc:
                last_error_message = f"网络超时，作品页面加载失败，请稍后重试: {exc}"
                self._set_error(last_error_message, kind="network")
            except requests.RequestException as exc:
                last_error_message = f"网络错误，请检查网络后重试: {exc}"
                self._set_error(last_error_message, kind="network")
            finally:
                if response is not None:
                    response.close()
        if last_error_message:
            return None
        self._set_error(
            "未能获取作品详情，作品可能不存在、已删除、仅自己可见，或分享链接已经失效，请重新复制最新分享链接后重试。",
            kind="api",
        )
        return None

    @staticmethod
    def _extract_browser_video_detail(page, aweme_id: str) -> dict | None:
        try:
            page_state = page.evaluate(
                """(targetAwemeId) => {
                    const video = document.querySelector('video');
                    const title = typeof document.title === 'string' ? document.title : '';
                    const currentSrc = video ? (video.currentSrc || video.src || '') : '';
                    const bitrateState =
                        window.playerBitrateSelectorRuler &&
                        window.playerBitrateSelectorRuler._current &&
                        typeof window.playerBitrateSelectorRuler._current === 'object'
                            ? window.playerBitrateSelectorRuler._current
                            : null;
                    return {
                        awemeId: targetAwemeId,
                        title,
                        currentSrc,
                        currentUrl: location.href,
                        bitrate: bitrateState && typeof bitrateState.bitrate === 'number' ? bitrateState.bitrate : 0,
                    };
                }""",
                aweme_id,
            )
        except PlaywrightError:
            return None

        return DouyinAPIClient._build_browser_video_detail(page_state)

    @staticmethod
    def _wait_for_browser_video_detail(page, aweme_id: str) -> dict | None:
        try:
            page.wait_for_function(
                """() => {
                    const video = document.querySelector('video');
                    if (!video) {
                        return false;
                    }
                    const currentSrc = video.currentSrc || video.src || '';
                    return currentSrc.startsWith('http') && !currentSrc.includes('douyin-pc-web/uuu_265.mp4');
                }""",
                timeout=12000,
            )
        except PlaywrightError:
            return None
        return DouyinAPIClient._extract_browser_video_detail(page, aweme_id)

    @staticmethod
    def _build_browser_video_detail(page_state: dict | None) -> dict | None:
        if not isinstance(page_state, dict):
            return None

        media_url = page_state.get("currentSrc") if isinstance(page_state.get("currentSrc"), str) else ""
        if not DouyinAPIClient._looks_like_real_video_url(media_url):
            return None

        aweme_id = str(page_state.get("awemeId") or "").strip()
        if not aweme_id:
            parsed = urlparse(media_url)
            aweme_id = parsed.path.rstrip("/").split("/")[-1]
        if not aweme_id:
            return None

        title = DouyinAPIClient._sanitize_browser_title(page_state.get("title") or "")
        bitrate = int(page_state.get("bitrate") or 0)
        video: dict = {"play_addr": {"url_list": [media_url]}}
        if bitrate > 0:
            video["bit_rate"] = [{"bit_rate": bitrate, "play_addr": {"url_list": [media_url]}}]

        return {
            "aweme_id": aweme_id,
            "aweme_type": 4,
            "desc": title,
            "author": {"sec_uid": "", "nickname": ""},
            "video": video,
        }

    def _resolve_url_with_browser(self, url: str) -> str | None:
        if sync_playwright is None:
            return None

        launch_kwargs = {"headless": True}
        if DEFAULT_EDGE_PATH.exists():
            launch_kwargs["executable_path"] = str(DEFAULT_EDGE_PATH)

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(**launch_kwargs)
                try:
                    context = browser.new_context(user_agent=self._get_headers()["user-agent"], locale="zh-CN")
                    self._add_auth_cookies_to_context(context)
                    page = context.new_page()
                    try:
                        try:
                            page.goto(url, wait_until="commit", timeout=5000)
                        except PlaywrightError:
                            page.goto(url, timeout=5000)

                        initial_url = url.strip().rstrip("/")
                        for _ in range(8):
                            page.wait_for_timeout(250)
                            current_url = page.url.strip()
                            if current_url and current_url.rstrip("/") != initial_url:
                                return current_url
                        current_url = page.url.strip()
                        if current_url and current_url.rstrip("/") != initial_url:
                            return current_url
                    finally:
                        page.close()
                        context.close()
                finally:
                    browser.close()
        except Exception as exc:
            self._set_error(f"网络超时，无法打开分享链接，请稍后重试: {exc}", kind="network")
            return None
        return None

    @staticmethod
    def _candidate_work_urls(aweme_id: str, page_url: str | None) -> list[str]:
        candidates: list[str] = []
        cleaned_page_url = page_url.strip() if isinstance(page_url, str) else ""
        if cleaned_page_url:
            candidates.append(cleaned_page_url)
        else:
            candidates.extend(
                (
                    f"https://www.douyin.com/note/{aweme_id}",
                    f"https://www.douyin.com/video/{aweme_id}",
                )
            )

        result: list[str] = []
        seen_keys: set[str] = set()
        for value in candidates:
            if not isinstance(value, str):
                continue
            cleaned = value.strip()
            if not cleaned or not cleaned.startswith("http"):
                continue
            key = cleaned.split("?", 1)[0].rstrip("/")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            result.append(cleaned)
        return result

    @staticmethod
    def _looks_like_short_douyin_url(url: str) -> bool:
        lowered = url.lower()
        return "v.douyin.com/" in lowered or "iesdouyin.com/share/" in lowered

    @staticmethod
    def _looks_like_real_video_url(url: str) -> bool:
        if not isinstance(url, str) or not url.startswith("http"):
            return False
        lowered = url.lower()
        if "douyin-pc-web/uuu_265.mp4" in lowered:
            return False
        return ".mp4" in lowered or "mime_type=video_mp4" in lowered or "__vid=" in lowered

    @staticmethod
    def _sanitize_browser_title(title: str) -> str:
        if not isinstance(title, str):
            return ""
        cleaned = title.strip()
        if cleaned.endswith(" - 抖音"):
            cleaned = cleaned[:-5].strip()
        return DouyinAPIClient._repair_mojibake_text(cleaned)

    @staticmethod
    def _detect_unavailable_aweme_page(page_content: str, aweme_id: str) -> str | None:
        if not isinstance(page_content, str) or not page_content.strip():
            return None
        if aweme_id in page_content and "videoDetail" in page_content:
            return None
        missing_markers = (
            "内容不存在",
            "作品不存在",
            "视频不见了",
            "该内容已删除",
            "无法查看该内容",
            "页面不存在",
            "您访问的页面不存在",
        )
        if any(marker in page_content for marker in missing_markers):
            return "作品不存在、已删除、仅自己可见，或分享链接已经失效，请重新复制最新分享链接后重试。"
        return None

    @staticmethod
    def _extract_aweme_detail_from_page_content(page_content: str, aweme_id: str) -> dict | None:
        for match in PACE_F_SCRIPT_PATTERN.finditer(page_content):
            payload = match.group(1)
            fragment = DouyinAPIClient._decode_render_payload(payload, aweme_id)
            if fragment is None:
                continue
            detail = DouyinAPIClient._find_rendered_aweme_detail(fragment, aweme_id)
            if detail:
                return detail
        return None

    @staticmethod
    def _decode_render_payload(payload: str, aweme_id: str):
        try:
            decoded = json.loads(f'"{payload}"')
        except json.JSONDecodeError:
            return None
        if aweme_id not in decoded:
            return None

        candidates = [decoded]
        unquoted = unquote(decoded)
        if unquoted != decoded:
            candidates.append(unquoted)

        for candidate in candidates:
            stripped = candidate.strip()
            if not stripped:
                continue
            try:
                if stripped.startswith("{") or stripped.startswith("["):
                    return json.loads(stripped)
                if ":" in stripped:
                    _, body = stripped.split(":", 1)
                    body = body.strip()
                    if body.startswith("{") or body.startswith("["):
                        return json.loads(body)
            except (ValueError, json.JSONDecodeError):
                continue
        return None

    @staticmethod
    def _find_rendered_aweme_detail(node, aweme_id: str) -> dict | None:
        if isinstance(node, dict):
            for key in ("videoDetail", "noteDetail"):
                candidate = node.get(key)
                if isinstance(candidate, dict):
                    candidate_aweme_id = str(candidate.get("awemeId") or candidate.get("aweme_id") or "")
                    if candidate_aweme_id == aweme_id:
                        return candidate

            aweme_block = node.get("aweme")
            current_aweme_id = str(node.get("awemeId") or node.get("aweme_id") or "")
            if current_aweme_id == aweme_id and isinstance(aweme_block, dict):
                detail = aweme_block.get("detail")
                if isinstance(detail, dict):
                    return detail

            detail = node.get("detail")
            if isinstance(detail, dict):
                detail_aweme_id = str(detail.get("awemeId") or detail.get("aweme_id") or "")
                if detail_aweme_id == aweme_id:
                    return detail

            for value in node.values():
                found = DouyinAPIClient._find_rendered_aweme_detail(value, aweme_id)
                if found:
                    return found
            return None

        if isinstance(node, list):
            for value in node:
                found = DouyinAPIClient._find_rendered_aweme_detail(value, aweme_id)
                if found:
                    return found
        return None

    @staticmethod
    def _normalize_rendered_aweme_detail(detail: dict) -> dict:
        if "aweme_id" in detail:
            return detail

        author_info = detail.get("authorInfo") if isinstance(detail.get("authorInfo"), dict) else {}
        images = detail.get("images") if isinstance(detail.get("images"), list) else []
        normalized_images = [
            image
            for image in (DouyinAPIClient._normalize_rendered_image_node(node) for node in images)
            if image is not None
        ]

        normalized = {
            "aweme_id": str(detail.get("awemeId") or detail.get("aweme_id") or ""),
            "aweme_type": detail.get("awemeType", detail.get("aweme_type")),
            "desc": DouyinAPIClient._repair_mojibake_text(
                detail.get("desc") or detail.get("itemTitle") or detail.get("caption") or ""
            ),
            "author": {
                "uid": author_info.get("uid") or detail.get("authorUserId"),
                "sec_uid": author_info.get("secUid") or author_info.get("sec_uid") or "",
                "nickname": DouyinAPIClient._repair_mojibake_text(author_info.get("nickname") or ""),
            },
        }

        video = DouyinAPIClient._normalize_rendered_video(detail.get("video"))
        if video:
            normalized["video"] = video

        if normalized_images:
            normalized["images"] = normalized_images
            normalized["image_post_info"] = {"images": normalized_images}

        return normalized

    @staticmethod
    def _normalize_rendered_image_node(image_node: dict) -> dict | None:
        if not isinstance(image_node, dict):
            return None

        normalized: dict = {}
        url_list = DouyinAPIClient._coerce_string_list(image_node.get("urlList") or image_node.get("url_list"))
        if url_list:
            normalized["url_list"] = url_list

        download_url_list = DouyinAPIClient._coerce_string_list(
            image_node.get("downloadUrlList") or image_node.get("download_url_list")
        )
        if download_url_list:
            normalized["download_url_list"] = download_url_list

        motion_video = DouyinAPIClient._normalize_rendered_video(
            image_node.get("video")
            or image_node.get("live_photo_video")
            or image_node.get("motion_photo")
            or image_node.get("motion_video")
        )
        if motion_video:
            normalized["video"] = motion_video

        return normalized or None

    @staticmethod
    def _normalize_rendered_video(video: dict | None) -> dict | None:
        if not isinstance(video, dict):
            return None

        normalized: dict = {}
        play_urls = DouyinAPIClient._extract_play_urls(video.get("playAddr") or video.get("play_addr"))
        if play_urls:
            normalized["play_addr"] = {"url_list": play_urls}

        play_h265_urls = DouyinAPIClient._extract_play_urls(video.get("playAddrH265") or video.get("play_addr_h265"))
        if play_h265_urls:
            normalized["play_addr_h265"] = {"url_list": play_h265_urls}

        play_api = video.get("playApi") or video.get("play_api")
        if isinstance(play_api, str) and play_api.startswith("http"):
            normalized["download_addr"] = {"url_list": [play_api]}

        bit_rate_list = video.get("bitRateList") or video.get("bit_rate")
        if isinstance(bit_rate_list, list):
            normalized_variants = []
            for variant in bit_rate_list:
                if not isinstance(variant, dict):
                    continue
                variant_urls = DouyinAPIClient._extract_play_urls(variant.get("playAddr") or variant.get("play_addr"))
                variant_h265_urls = DouyinAPIClient._extract_play_urls(
                    variant.get("playAddrH265") or variant.get("play_addr_h265")
                )
                normalized_variant = {
                    "bit_rate": variant.get("bitRate", variant.get("bit_rate")) or 0,
                    "gear_name": variant.get("gearName", variant.get("gear_name")) or "",
                    "width": variant.get("width") or 0,
                    "height": variant.get("height") or 0,
                }
                if variant_urls:
                    normalized_variant["play_addr"] = {"url_list": variant_urls}
                if variant_h265_urls:
                    normalized_variant["play_addr_h265"] = {"url_list": variant_h265_urls}
                if "play_addr" in normalized_variant or "play_addr_h265" in normalized_variant:
                    normalized_variants.append(normalized_variant)
            if normalized_variants:
                normalized["bit_rate"] = normalized_variants

        return normalized or None

    @staticmethod
    def _extract_play_urls(node) -> list[str]:
        if isinstance(node, str) and node.startswith("http"):
            return [node]
        if isinstance(node, list):
            urls: list[str] = []
            for value in node:
                urls.extend(DouyinAPIClient._extract_play_urls(value))
            return DouyinAPIClient._coerce_string_list(urls)
        if isinstance(node, dict):
            src = node.get("src")
            if isinstance(src, str) and src.startswith("http"):
                return [src]
            for key in ("url_list", "urlList", "play_addr", "playAddr", "download_url_list", "downloadUrlList"):
                if key in node:
                    return DouyinAPIClient._extract_play_urls(node.get(key))
        return []

    @staticmethod
    def _coerce_string_list(values) -> list[str]:
        if isinstance(values, str):
            return [values] if values.startswith("http") else []
        if not isinstance(values, list):
            return []

        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value.startswith("http") or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    @staticmethod
    def _repair_mojibake_text(value: str) -> str:
        if not isinstance(value, str) or not value:
            return ""
        if any("\u4e00" <= char <= "\u9fff" for char in value):
            return value
        try:
            repaired = value.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return value
        if any("\u4e00" <= char <= "\u9fff" for char in repaired):
            return repaired
        return value

    def _request_json(
        self,
        url: str,
        params: dict | None = None,
        *,
        emit_error: bool = True,
        sign: bool = False,
        referer: str | None = None,
        timeout_seconds: int = 10,
        max_attempts: int = 3,
    ) -> dict | None:
        response = None
        request_url = url
        if sign and params:
            request_url = f"{url}?{urlencode(params)}"
            request_url, _, _ = generate_x_bogus(request_url, self.user_agent)

        for attempt in range(max_attempts):
            try:
                headers = self._get_headers()
                if referer:
                    headers["referer"] = referer

                response = self.session.get(
                    request_url if sign else url,
                    params=None if sign else params,
                    headers=headers,
                    timeout=timeout_seconds,
                )
                if response.status_code in {403, 429, 500, 502, 503, 504} and attempt < max_attempts - 1:
                    time.sleep(1.0 * (2**attempt))
                    continue
                response.raise_for_status()
                if not response.text.strip():
                    raise JSONDecodeError("empty response body", response.text, 0)
                data = response.json()
                self._clear_error()
                return data
            except JSONDecodeError:
                snippet = (response.text[:200] if response is not None else "").strip()
                error_msg = f"接口返回异常，服务器响应为空或不是 JSON: {snippet or '<empty>'}"
                self._set_error(error_msg, kind="api")
                if attempt < max_attempts - 1:
                    time.sleep(0.6 * (2**attempt))
                    continue
                if emit_error:
                    self._emit_error(error_msg)
                return None
            except requests.Timeout as exc:
                if attempt < max_attempts - 1:
                    time.sleep(0.8 * (2**attempt))
                    continue
                error_msg = f"网络超时，请检查网络后重试: {exc}"
                self._set_error(error_msg, kind="network")
                if emit_error:
                    self._emit_error(error_msg)
                return None
            except requests.RequestException as exc:
                if attempt < max_attempts - 1:
                    time.sleep(0.8 * (2**attempt))
                    continue
                error_msg = f"网络错误，请检查网络后重试: {exc}"
                self._set_error(error_msg, kind="network")
                if emit_error:
                    self._emit_error(error_msg)
                return None
            except Exception as exc:
                error_msg = f"处理响应时出错: {exc}"
                self._set_error(error_msg, kind="api")
                if emit_error:
                    self._emit_error(error_msg)
                return None
        return None

    @staticmethod
    def _extract_aweme_detail(data: dict | None) -> dict | None:
        if not isinstance(data, dict):
            return None

        for key in ("aweme_detail", "detail"):
            detail = data.get(key)
            if isinstance(detail, dict):
                return detail
        return None

    def _emit_error(self, message: str) -> None:
        if self.error_callback:
            self.error_callback(message)
        else:
            print(message)

    def _set_error(self, message: str, *, kind: str) -> None:
        self.last_error = message
        self.last_error_kind = kind

    def _clear_error(self) -> None:
        self.last_error = None
        self.last_error_kind = None
