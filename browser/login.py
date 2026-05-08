"""
Cookie 注入与登录态验证。
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://mcenter.ke.com"


def parse_cookie_string(raw: str) -> Optional[list[dict]]:
    """解析 Cookie 字符串为 Playwright cookie 对象列表。

    支持多种格式：
    - 纯 cookie 字符串: "name1=val1; name2=val2"
    - HTTP headers 格式
    - JSON 字符串: '[{name:"x",value:"y"}]'
    """
    raw = raw.strip()
    if not raw:
        return None

    # 尝试 JSON 格式
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            for c in parsed:
                c.setdefault("domain", ".ke.com")
                c.setdefault("path", "/")
            return parsed
        except json.JSONDecodeError:
            pass

    # 尝试 HTTP headers 格式（key: value 对）
    if "\n" in raw:
        lines = raw.split("\n")
        cookie_line = ""
        for i, line in enumerate(lines):
            if line.strip().lower().startswith("cookie"):
                cookie_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                break
        if cookie_line:
            raw = cookie_line

    # 标准 cookie 字符串: "name=value; name2=value2"
    cookies = []
    for item in raw.split("; "):
        item = item.strip()
        if "=" not in item:
            continue
        name, _, value = item.partition("=")
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": ".ke.com",
            "path": "/",
        })
    return cookies if cookies else None


def load_cookie_from_file(path: str, city: str = None) -> Optional[list[dict]]:
    """从文件加载 Cookie。

    支持两种格式:
    1. 单城市文件: 直接包含 cookie 字符串
    2. 多城市文件: 每行以 "城市名：cookie字符串" 格式，
       可通过 city 参数指定城市。

    :param path: 文件路径
    :param city: 目标城市名（用于多城市文件）
    """
    import re

    filepath = Path(path)
    if not filepath.exists():
        logger.error("Cookie 文件不存在: %s", path)
        return None

    content = filepath.read_text(encoding="utf-8").strip()

    # 检测是否多城市文件: 有 "城市名：cookie" 格式的行
    multi_city_pattern = re.compile(r'^[^\s]+[：:].+;.+')
    lines = content.split("\n")

    multi_city_lines = []
    for line in lines:
        line = re.sub(r'^\d+\t', '', line.strip())
        if multi_city_pattern.match(line):
            if '：' in line or ':' in line:
                multi_city_lines.append(line)

    if len(multi_city_lines) > 1:
        # 多城市文件
        logger.info("检测到多城市 Cookie 文件 (%d 个城市)", len(multi_city_lines))

        if city:
            for line in multi_city_lines:
                sep = '：' if '：' in line else ':'
                city_name = line.split(sep, 1)[0].strip()
                if city_name == city:
                    cookie_str = line.split(sep, 1)[1].strip()
                    logger.info("已选择城市: %s", city)
                    return parse_cookie_string(cookie_str)
            logger.warning("未找到城市 '%s' 的 Cookie，使用第一个", city)

        # 使用第一个城市
        sep = '：' if '：' in multi_city_lines[0] else ':'
        city_name = multi_city_lines[0].split(sep, 1)[0].strip()
        cookie_str = multi_city_lines[0].split(sep, 1)[1].strip()
        logger.info("使用默认城市: %s", city_name)
        return parse_cookie_string(cookie_str)

    return parse_cookie_string(content)


async def verify_login(page) -> bool:
    """验证登录态是否有效。

    检测页面是否包含登录用户信息和导航菜单，
    而非登录表单。
    """
    try:
        await page.wait_for_timeout(2000)
        content = await page.content()

        # 如果出现 forbidden / 登录页，说明未登录
        if "/forbidden" in page.url or "密码" in content:
            logger.error("登录态失效: 检测到 forbidden 或登录页")
            return False

        # 检测"退出登录"或"欢迎"文本确认已登录
        body_text = await page.locator("body").inner_text()
        if "退出登录" in body_text or "欢迎" in body_text or "服务单管理" in body_text:
            logger.info("登录态验证通过")
            return True

        logger.warning("登录态验证不确定，但未检测到登录页")
        return True
    except Exception as e:
        logger.error("登录态验证异常: %s", e)
        return False
