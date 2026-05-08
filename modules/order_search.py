"""
模块 C: 单号识别与搜索框填充。

使用直接 URL 导航方式替代搜索表单交互，
因为实际测试中发现搜索表单在 DOM 中隐藏。
"""
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


def classify_order(order_id: str) -> str:
    """根据单号前缀判断类型。

    :return: 'order' (T开头) / 'service' (S开头) / 'unknown'
    """
    if not order_id:
        return "unknown"
    prefix = order_id[0].upper()
    if prefix == "T":
        return "order"
    elif prefix == "S":
        return "service"
    return "unknown"


async def search_by_order_id(page: Page, order_id: str) -> bool:
    """
    通过直接 URL 导航至订单详情页。

    因为已验证的可靠方案是直接 URL 访问，跳过了搜索表单。

    :param page: Playwright Page 对象
    :param order_id: 单号
    :return: 是否访问成功
    """
    order_type = classify_order(order_id)
    if order_type == "unknown":
        logger.warning("未知单号前缀: %s", order_id)
        return False

    url = f"https://mcenter.ke.com/new/#/maintain/provider/detail?code={order_id}"
    logger.info("导航至详情页: %s", url[:80])

    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        body = await page.locator("body").inner_text()
        found = order_id in body
        if found:
            logger.info("订单 %s 已找到", order_id)
        else:
            logger.warning("订单 %s 未在结果中找到", order_id)
        return found
    except Exception as e:
        logger.error("搜索导航异常: %s", e)
        return False
