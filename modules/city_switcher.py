"""
模块 B: 城市选择器交互。

通过 hover 城市下拉框并点击目标城市进行切换。
如果无法切换（如权限不足），将记录错误。
"""
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def switch_city(page: Page, city_name: str) -> bool:
    """切换至指定城市工作台。

    通过 hover 触发城市下拉框，然后点击目标城市选项。

    :param page: Playwright Page 对象
    :param city_name: 目标城市名，如 "杭州市"
    :return: 是否切换成功
    """
    # 先尝试检测是否需要切换
    welcome = page.locator("text=/欢迎，.*维修/").first
    if await welcome.count() > 0:
        current = await welcome.text_content()
        if city_name in current:
            logger.info("当前已是目标城市: %s", city_name)
            return True

    # Hover 城市下拉触发器
    trigger = page.locator(".ant-dropdown-trigger.drop-text").first
    await trigger.hover()
    await page.wait_for_timeout(2000)

    # 查找目标城市选项
    city_option = page.locator(f"text=北京永基维修服务有限公司（{city_name}）")
    if await city_option.count() == 0:
        city_option = page.locator(f"text={city_name}").first

    if await city_option.count() > 0 and await city_option.first.is_visible():
        await city_option.first.click()
        await page.wait_for_timeout(4000)

        # 验证
        welcome_after = page.locator("text=/欢迎，.*维修/").first
        if await welcome_after.count() > 0:
            txt = await welcome_after.text_content()
            if city_name in txt:
                logger.info("城市切换成功: %s", city_name)
                return True

    logger.warning("城市切换失败: %s（可能权限不足或未在下拉列表中）", city_name)
    return False
