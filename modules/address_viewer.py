"""
模块 E: 隐式地址查看。

点击订单详情页中"服务地址"旁的"查看"按钮，
通过 Ant Design Popover 获取完整地址。
"""
import logging
import re
from playwright.async_api import Page

logger = logging.getLogger(__name__)

DETAIL_URL = "https://mcenter.ke.com/new/#/maintain/provider/detail?code={order_id}"


async def get_full_address(page: Page, order_id: str) -> str:
    """
    打开订单详情页，点击"查看"获取完整地址。

    流程:
    1. 导航到订单详情页 URL
    2. 找到掩码地址旁的"查看"按钮（*** + 城市名）
    3. 点击并等待 Popover 显示完整地址
    4. 提取地址文本并返回

    :param page: Playwright Page 对象
    :param order_id: 单号 (S 或 T 开头)
    :return: 完整地址字符串，失败返回 "ERROR: 原因"
    """
    try:
        url = DETAIL_URL.format(order_id=order_id)
        logger.info("正在打开详情页: %s", url)

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        body = await page.locator("body").inner_text()

        if order_id not in body:
            return f"ERROR: 订单 {order_id} 未在详情页找到"

        # 查找地址"查看"按钮
        # 地址格式: "西安灞桥阳光************* 查看"
        # 手机号格式: "181****9945 查看"
        # 区分：地址的 *** 更长（≥8个），并且前面有城市/区名
        spans = page.locator('span:text-is("查看")')
        for i in range(await spans.count()):
            el = spans.nth(i)
            if not await el.is_visible():
                continue

            parent_text = await el.locator("xpath=..").inner_text()
            view_pos = parent_text.find("查看")
            before_view = parent_text[:view_pos]
            asterisk_count = len(re.findall(r"\*", before_view))

            # 地址掩码 ≥ 8 个星号
            if asterisk_count >= 8:
                logger.info("找到地址'查看'按钮，掩码长度=%d", asterisk_count)

                await el.scroll_into_view_if_needed()
                await page.wait_for_timeout(300)
                await el.click()
                await page.wait_for_timeout(2000)

                # 提取 Popover 中的完整地址
                addr = await page.evaluate('''() => {
                    const popovers = document.querySelectorAll(
                        '.ant-popover:not(.ant-popover-hidden)'
                    );
                    for (const p of popovers) {
                        const t = p.textContent?.trim();
                        if (t && !t.includes('***') && t.length > 3) {
                            return t;
                        }
                    }
                    return null;
                }''')

                if addr:
                    logger.info("地址获取成功: %s", addr)
                    return addr
                else:
                    logger.warning("Popover 未找到完整地址文本")
                    return "ERROR: 查看弹窗未显示完整地址"

        logger.warning("未找到地址'查看'按钮")
        return "ERROR: 地址不可查看（未找到查看按钮）"

    except Exception as e:
        logger.error("获取地址异常: %s", e)
        return f"ERROR: {str(e)[:100]}"
