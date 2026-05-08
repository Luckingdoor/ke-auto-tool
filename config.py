"""
配置管理：从环境变量或 .env 文件读取配置。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(Path(__file__).parent / ".env")


def get_cookies() -> list[dict]:
    """获取 Cookie 列表。

    优先级: COOKIE_JSON > COOKIE_FILE
    """
    from browser.login import parse_cookie_string, load_cookie_from_file

    # 方式1: 直接 JSON 字符串
    cookie_json = os.getenv("COOKIE_JSON")
    if cookie_json:
        cookies = parse_cookie_string(cookie_json)
        if cookies:
            return cookies

    # 方式2: 从文件加载
    cookie_file = os.getenv("COOKIE_FILE", "cookie.txt")
    if cookie_file:
        filepath = Path(cookie_file)
        if not filepath.is_absolute():
            filepath = Path(__file__).parent / cookie_file
        if filepath.exists():
            return load_cookie_from_file(str(filepath))

    raise RuntimeError(
        "未找到 Cookie 配置。请在 .env 中设置 COOKIE_JSON 或 COOKIE_FILE"
    )


def get_config() -> dict:
    """获取所有配置项。"""
    return {
        "headless": os.getenv("HEADLESS", "false").lower() == "true",
        "city": os.getenv("CITY", "").strip() or None,
        "query_interval": float(os.getenv("QUERY_INTERVAL", "2")),
    }
