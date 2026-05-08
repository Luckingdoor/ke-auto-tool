"""
Playwright 浏览器上下文管理。
"""
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .login import verify_login

logger = logging.getLogger(__name__)

BASE_URL = "https://mcenter.ke.com/new#/workbench"


class BrowserContext:
    """管理 Playwright 浏览器生命周期与 Cookie 注入。"""

    def __init__(self, cookies: list[dict], headless: bool = False):
        self._cookies = cookies
        self._headless = headless
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def __aenter__(self) -> "BrowserContext":
        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        self._context = await self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        # 隐藏自动化特征
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
        )

        # 注入 Cookie
        await self._context.add_cookies(self._cookies)
        logger.info("已注入 %d 条 Cookie", len(self._cookies))

        # 打开页面
        self._page = await self._context.new_page()
        await self._page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await self._page.wait_for_timeout(3000)

        # 验证登录态
        if not await verify_login(self._page):
            raise RuntimeError("登录态验证失败，Cookie 可能已过期")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("浏览器未初始化，请使用 async with")
        return self._page

    def get_current_city(self) -> str:
        """从页面提取当前城市名称。"""
        # 从欢迎文本提取: "欢迎，刘勇浩-北京永基维修服务有限公司（北京市）"
        # 返回: "北京市"
        pass
