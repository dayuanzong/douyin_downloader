
import re

def extract_sec_user_id(url: str) -> str | None:
    """
    从抖音分享链接中提取 sec_user_id

    :param url: 抖音分享链接
    :return: sec_user_id, 如果没有找到则返回 None
    """
    # 匹配 sec_uid=... 的格式
    match = re.search(r"sec_uid=([^&]+)", url)
    if match:
        return match.group(1)
    
    # 匹配 /user/... 的格式
    match = re.search(r"/user/([^/?]+)", url)
    if match:
        return match.group(1)

    return None
