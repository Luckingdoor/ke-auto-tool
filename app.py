"""
贝壳维修工作台自动化查询工具 - Web 界面
基于 Streamlit + Playwright，支持持久化登录态与批量查询。
"""
import asyncio
import io
import re
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from playwright.async_api import async_playwright

st.set_page_config(page_title="贝壳工作台查询工具", page_icon="🏠", layout="wide")

# 首次运行时安装 Chromium（Streamlit Cloud 环境）
@st.cache_resource
def install_chromium():
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True)
    return True

install_chromium()

# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════

CITIES = ["北京", "广州", "杭州", "南京", "武汉", "西安"]

# ═══════════════════════════════════════════════════════════════
# Cookie 解析
# ═══════════════════════════════════════════════════════════════

def parse_cookie_string(raw: str) -> list[dict]:
    cookies = []
    for item in raw.strip().split("; "):
        if "=" not in item:
            continue
        name, _, value = item.partition("=")
        cookies.append({"name": name.strip(), "value": value.strip(), "domain": ".ke.com", "path": "/"})
    return cookies

def parse_multi_city_file(content: str) -> dict[str, list[dict]]:
    """解析多城市 Cookie 文件，返回 {城市: cookie列表} 字典。"""
    lines = content.strip().split("\n")
    city_cookies = {}
    for line in lines:
        line = re.sub(r'^\d+\t', '', line.strip())
        if '：' in line and ';' in line:
            city, cookie_str = line.split('：', 1)
            city = city.strip()
            cookies = parse_cookie_string(cookie_str.strip())
            if cookies:
                city_cookies[city] = cookies
    return city_cookies

def parse_pasted_orders(text: str) -> list[str]:
    """从粘贴的文本中提取有效单号（S或T开头，自动去空格）。"""
    # 按空白字符和换行分割
    tokens = re.split(r'[\s,;，；]+', text.strip())
    orders = []
    seen = set()
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        if t[0].upper() in ('S', 'T') and len(t) > 10:
            if t not in seen:
                orders.append(t)
                seen.add(t)
    return orders

# ═══════════════════════════════════════════════════════════════
# 浏览器与地址查询
# ═══════════════════════════════════════════════════════════════

async def verify_one_city(city: str, cookies: list[dict]) -> str:
    """验证单个城市的 Cookie 是否有效。

    返回: "ok" / "invalid" / "network_error"
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => false });")
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()
        try:
            await page.goto("https://mcenter.ke.com/new#/workbench", wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(3000)
            body = await page.locator("body").inner_text()
            has_menu = "服务单管理" in body or "退出登录" in body
            welcome = await page.locator("text=/欢迎，.*维修/").first.text_content() if await page.locator("text=/欢迎，.*维修/").count() > 0 else ""
            city_ok = city in welcome if welcome else True
            return "ok" if (has_menu and city_ok) else "invalid"
        except Exception:
            return "network_error"
        finally:
            await browser.close()


async def verify_all_cities(city_cookies: dict[str, list[dict]], progress_placeholder=None) -> dict[str, str]:
    """逐一验证所有城市的 Cookie，返回 {城市: "ok"/"invalid"/"network_error"}。"""
    results = {}
    cities = list(city_cookies.keys())
    for idx, city in enumerate(cities):
        if progress_placeholder:
            progress_placeholder.text(f"正在验证: {city} ({idx + 1}/{len(cities)}) ...")
        results[city] = await verify_one_city(city, city_cookies[city])
    if progress_placeholder:
        ok_count = sum(1 for v in results.values() if v == "ok")
        net_err = sum(1 for v in results.values() if v == "network_error")
        invalid = sum(1 for v in results.values() if v == "invalid")
        if net_err and not invalid:
            progress_placeholder.text(f"⚠️ 网络不通（{net_err}城），Cookie 已加载但未验证 — 查询时会报具体错误")
        elif invalid:
            failed_names = [c for c, v in results.items() if v == "invalid"]
            progress_placeholder.text(f"⚠️ {ok_count}/{len(results)} 通过 | 失败: {', '.join(failed_names)}")
        else:
            progress_placeholder.text(f"✅ 全部 {len(results)} 个城市验证通过")
    return results


async def get_address(order_id: str, cookies: list[dict], headless: bool = True) -> str:
    """通过直接 URL 访问订单详情页，点击"查看"获取完整地址。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => false });")
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()

        try:
            url = f"https://mcenter.ke.com/new/#/maintain/provider/detail?code={order_id}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            body = await page.locator("body").inner_text()
            if order_id not in body:
                return "ERROR: 订单未找到，请检查单号或城市是否正确"

            spans = page.locator('span:text-is("查看")')
            for i in range(await spans.count()):
                el = spans.nth(i)
                if not await el.is_visible():
                    continue
                parent_text = await el.locator("xpath=..").inner_text()
                asterisks = len(re.findall(r'\*', parent_text[:parent_text.find('查看')]))

                if asterisks >= 8:
                    await el.scroll_into_view_if_needed()
                    await page.wait_for_timeout(300)
                    await el.click()
                    await page.wait_for_timeout(2000)

                    addr = await page.evaluate('''() => {
                        for (const p of document.querySelectorAll('.ant-popover:not(.ant-popover-hidden)')) {
                            const t = p.textContent?.trim();
                            if (t && !t.includes('***')) return t;
                        }
                        return null;
                    }''')
                    if addr:
                        return addr

            return "ERROR: 未找到地址查看按钮"
        except Exception as e:
            return f"ERROR: {str(e)[:100]}"
        finally:
            await browser.close()


# ═══════════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════════

st.title("🏠 贝壳维修工作台自动化查询工具")

# session state 初始化
defaults = {
    'cookies': None,
    'city': None,
    'all_city_cookies': {},
    'cookie_errors': {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def switch_active_city(city_name: str):
    """切换当前活跃城市，使用对应的已验证 Cookie。"""
    if city_name in st.session_state.all_city_cookies:
        st.session_state.city = city_name
        st.session_state.cookies = st.session_state.all_city_cookies[city_name]
        return True
    return False

# ── 侧边栏：登录 ────────────────────────────────────────────

with st.sidebar:
    st.header("🔑 登录配置")

    with st.expander("📖 如何获取 Cookie？", expanded=False):
        st.markdown("""
        **操作步骤：**

        1. 打开 Chrome/Edge 浏览器，访问 [贝壳工作台](https://mcenter.ke.com) 并登录
        2. 登录后按 `F12` → 点击 **Console**（控制台）标签
        3. 输入以下命令并回车：
        """)
        st.code("copy(document.cookie)", language="javascript")
        st.markdown("""
        4. Cookie 已复制到剪贴板，回到本页粘贴即可

        > Cookie 有效期约数小时，过期后重新获取即可。
        > 如查询报错"订单未找到"，通常是因为 Cookie 过期。
        """)

    st.divider()

    login_method = st.radio(
        "选择方式",
        ["📋 粘贴 Cookie", "📁 上传 Cookie 文件"],
        label_visibility="collapsed"
    )

    if login_method == "📋 粘贴 Cookie":
        cookie_text = st.text_area(
            "Cookie 字符串",
            height=100,
            placeholder="crosSdkDT2019DeviceId=...; supplier_ke_token=..."
        )
        if st.button("加载并验证", type="primary", use_container_width=True):
            if cookie_text.strip():
                cookies = parse_cookie_string(cookie_text)
                if not cookies:
                    st.error("格式错误，请检查后重新粘贴")
                else:
                    with st.spinner("正在验证 Cookie 有效性..."):
                        status = asyncio.run(verify_one_city("默认", cookies))
                    if status == "invalid":
                        st.error("Cookie 无效或已过期，请重新获取")
                    else:
                        if status == "network_error":
                            st.warning("⚠️ 网络不通，Cookie 已加载但未验证")
                        st.session_state.cookies = cookies
                        st.session_state.all_city_cookies = {"默认": cookies}
                        st.rerun()

    else:
        cookie_file = st.file_uploader("上传 .txt 文件", type=["txt"], label_visibility="collapsed")
        if cookie_file:
            content = cookie_file.read().decode("utf-8")
            # 检测是否多城市文件
            city_cookies_parsed = parse_multi_city_file(content)
            multi = len(city_cookies_parsed) > 1

            if multi:
                st.caption(f"📂 检测到 **{len(city_cookies_parsed)}** 个城市: {'、'.join(city_cookies_parsed.keys())}")

            if st.button("加载并验证", type="primary", use_container_width=True):
                if multi:
                    # 多城市文件：逐一验证所有城市
                    status_placeholder = st.empty()
                    progress_bar = st.progress(0)

                    status_placeholder.text("正在验证所有城市...")
                    results = asyncio.run(verify_all_cities(
                        city_cookies_parsed, status_placeholder
                    ))

                    # 存储结果：ok 和 network_error 都接受
                    passed = {}
                    failed = {}
                    for city, status in results.items():
                        if status == "invalid":
                            failed[city] = "Cookie 无效或已过期"
                        else:
                            passed[city] = city_cookies_parsed[city]

                    st.session_state.all_city_cookies = passed
                    st.session_state.cookie_errors = failed

                    if passed:
                        first_city = list(passed.keys())[0]
                        st.session_state.cookies = passed[first_city]
                        st.session_state.city = first_city

                    # 显示结果
                    has_net_err = any(s == "network_error" for s in results.values())
                    if failed:
                        failed_names = '、'.join(failed.keys())
                        st.error(f"❌ 验证失败: {failed_names} — 请更新这些城市的 Cookie")
                    if passed:
                        if has_net_err and not failed:
                            st.warning("⚠️ 网络不通，Cookie 已加载但无法验证 — 实际查询时会报具体错误")
                        else:
                            st.success(f"✅ 全部 {len(passed)} 个城市验证通过")
                    progress_bar.progress(1.0)
                    st.rerun()

                else:
                    # 单城市文件
                    cookies = parse_cookie_string(content)
                    if not cookies:
                        st.error("解析失败，请检查文件格式")
                    else:
                        with st.spinner("正在验证 Cookie ..."):
                            status = asyncio.run(verify_one_city("默认", cookies))
                        if status == "invalid":
                            st.error("Cookie 无效或已过期，请重新获取")
                        else:
                            if status == "network_error":
                                st.warning("⚠️ 网络不通，Cookie 已加载但未验证")
                            st.session_state.cookies = cookies
                            st.session_state.all_city_cookies = {"默认": cookies}
                            st.rerun()

    st.divider()

    # ── 登录状态显示 ────────────────────────────────────────

    if st.session_state.cookies:
        all_cities = st.session_state.all_city_cookies
        errors = st.session_state.cookie_errors
        active = st.session_state.city

        if len(all_cities) > 1:
            # 多城市模式：显示城市切换下拉框
            st.selectbox(
                "📍 切换城市",
                options=list(all_cities.keys()),
                index=list(all_cities.keys()).index(active) if active in all_cities else 0,
                key="city_switcher",
                on_change=lambda: switch_active_city(st.session_state.city_switcher),
                label_visibility="collapsed"
            )
            st.success(f"🟢 {len(all_cities)} 个城市已就绪")
        else:
            st.success(f"🟢 已就绪 | {len(st.session_state.cookies)} 条 Cookie")
            if active:
                st.caption(f"📍 {active}")

        if errors:
            failed_names = '、'.join(errors.keys())
            st.error(f"❌ {failed_names} — Cookie 无效，需更新文件后重新验证")
    else:
        st.warning("🔴 请先加载 Cookie")

    st.divider()
    st.caption("v1.1 | 仅执行查询操作，不修改任何数据")

# ── 主区域：查询 ────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs(["🔍 单条查询", "📋 粘贴多条单号", "📊 上传表格查询"])

# ── Tab 1：单条查询 ────────────────────────────────────────

with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        order_id = st.text_input(
            "单号", placeholder="S01002026050817622184204",
            label_visibility="collapsed", key="single_oid"
        )
    with col2:
        available_cities = list(st.session_state.all_city_cookies.keys()) if st.session_state.all_city_cookies else (CITIES if st.session_state.cookies else [])
        default_idx = available_cities.index(st.session_state.city) if st.session_state.city in available_cities else 0
        city = st.selectbox(
            "城市", options=available_cities,
            index=default_idx,
            label_visibility="collapsed", key="single_city"
        ) if available_cities else None

    if st.button("查询地址", type="primary", use_container_width=True, disabled=not st.session_state.cookies):
        oid = order_id.strip()
        if not oid:
            st.error("请输入单号")
        elif oid[0].upper() not in ('S', 'T'):
            st.error("单号必须以 S 或 T 开头")
        else:
            # 使用选中城市对应的 Cookie
            query_cookies = st.session_state.all_city_cookies.get(city, st.session_state.cookies)
            with st.spinner(f"正在查询 {oid} ..."):
                addr = asyncio.run(get_address(oid, query_cookies, headless=True))
            if addr.startswith("ERROR"):
                st.error(addr)
            else:
                st.success(addr)
                st.code(f"单号: {oid}\n地址: {addr}", language="")

# ── Tab 2：粘贴多条单号 ────────────────────────────────────

with tab2:
    st.markdown("粘贴多个单号，自动识别 **S/T 开头**的单号，空格/换行分隔均可")

    col1, col2 = st.columns(2)
    with col1:
        paste_text = st.text_area(
            "粘贴单号",
            height=150,
            placeholder="S01002026050713164828552\nS01002026050715022181615\nS01002026050713204448988\nS01002026050817146145523\nS01002026050715253112955",
            label_visibility="collapsed",
            key="paste_orders"
        )
    with col2:
        available_cities = list(st.session_state.all_city_cookies.keys()) if st.session_state.all_city_cookies else (CITIES if st.session_state.cookies else [])
        default_idx = available_cities.index(st.session_state.city) if st.session_state.city in available_cities else 0
        paste_city = st.selectbox(
            "城市", options=available_cities,
            index=default_idx,
            label_visibility="collapsed", key="paste_city"
        ) if available_cities else None
        interval2 = st.slider("查询间隔（秒）", 1, 10, 2, key="interval2")

    if paste_text.strip():
        parsed = parse_pasted_orders(paste_text)
        if parsed:
            st.caption(f"✅ 识别到 **{len(parsed)}** 个有效单号")
            if len(parsed) <= 10:
                st.text(", ".join(parsed))
            else:
                st.text(", ".join(parsed[:10]) + f" ... 等 {len(parsed)} 个")

            if st.button("开始查询", type="primary", use_container_width=True, disabled=not st.session_state.cookies, key="btn_paste"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                result_placeholder = st.empty()
                results = []

                query_cookies = st.session_state.all_city_cookies.get(paste_city, st.session_state.cookies)

                total = len(parsed)
                for idx, oid in enumerate(parsed):
                    fraction = (idx + 1) / total
                    progress_bar.progress(fraction)
                    status_text.text(f"🔍 查询中: {idx + 1}/{total} — {oid}")

                    addr = asyncio.run(get_address(oid, query_cookies, headless=True))
                    results.append({"单号": oid, "查询地址": addr})

                    # 每查完一条立刻刷新表格
                    result_placeholder.dataframe(
                        pd.DataFrame(results), use_container_width=True, hide_index=True
                    )

                    if idx < total - 1:
                        time.sleep(interval2 + random.uniform(0, 1))

                success = sum(1 for r in results if not r["查询地址"].startswith("ERROR"))
                failed = len(results) - success
                progress_bar.progress(1.0)
                status_text.text(f"✅ 完成! 共 {total} 条 | 成功 {success} | 失败 {failed}")

                # 下载
                df_out = pd.DataFrame(results)
                output = io.BytesIO()
                df_out.to_excel(output, index=False)
                st.download_button(
                    "📥 下载结果",
                    data=output.getvalue(),
                    file_name=f"查询结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_paste"
                )
        else:
            st.warning("未识别到有效单号（需 S 或 T 开头）")

# ── Tab 3：上传表格查询 ────────────────────────────────────

with tab3:
    st.markdown("上传 Excel 或 CSV 文件，**必须包含 `单号` 列**（S 或 T 开头）")

    col1, col2 = st.columns(2)
    with col1:
        uploaded = st.file_uploader("选择文件", type=["xlsx", "xls", "csv"], label_visibility="collapsed", key="file_upload")
    with col2:
        available_cities = list(st.session_state.all_city_cookies.keys()) if st.session_state.all_city_cookies else (CITIES if st.session_state.cookies else [])
        default_idx = available_cities.index(st.session_state.city) if st.session_state.city in available_cities else 0
        batch_city = st.selectbox(
            "城市", options=available_cities,
            index=default_idx,
            label_visibility="collapsed", key="file_city"
        ) if available_cities else None
        interval3 = st.slider("查询间隔（秒）", 1, 10, 2, key="interval3")

    if uploaded:
        try:
            if uploaded.name.endswith('.csv'):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
        except Exception as e:
            st.error(f"文件读取失败: {e}")
            st.stop()

        if "单号" not in df.columns:
            st.error(f"缺少 '单号' 列。可用列: {', '.join(df.columns.tolist())}")
            st.stop()

        # 提取有效单号
        df["单号"] = df["单号"].astype(str).str.strip()
        all_oids = df["单号"].tolist()
        valid_oids = [o for o in all_oids if o and o != "nan" and o[0].upper() in ('S', 'T')]
        invalid_count = len(all_oids) - len(valid_oids)

        st.caption(
            f"共 {len(all_oids)} 条记录"
            + (f"，其中 {invalid_count} 条无效单号将被跳过" if invalid_count else "")
            + f" | 预计耗时约 {len(valid_oids) * (interval3 + 3)} 秒"
        )

        if st.button("开始批量查询", type="primary", use_container_width=True, disabled=not st.session_state.cookies, key="btn_file"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            result_placeholder = st.empty()
            results = []

            query_cookies = st.session_state.all_city_cookies.get(batch_city, st.session_state.cookies)

            total = len(valid_oids)
            for idx, oid in enumerate(valid_oids):
                fraction = (idx + 1) / total
                progress_bar.progress(fraction)
                status_text.text(f"🔍 查询中: {idx + 1}/{total} — {oid}")

                addr = asyncio.run(get_address(oid, query_cookies, headless=True))
                results.append({"单号": oid, "查询地址": addr})

                result_placeholder.dataframe(
                    pd.DataFrame(results), use_container_width=True, hide_index=True
                )

                if idx < total - 1:
                    time.sleep(interval3 + random.uniform(0, 1))

            # 回填结果
            addr_map = {r["单号"]: r["查询地址"] for r in results}
            df["查询地址"] = df["单号"].map(addr_map).fillna("ERROR: 无效单号")

            success = sum(1 for r in results if not r["查询地址"].startswith("ERROR"))
            failed = len(results) - success

            progress_bar.progress(1.0)
            status_text.text(f"✅ 完成! 共 {total} 条 | 成功 {success} | 失败 {failed}")

            output = io.BytesIO()
            df.to_excel(output, index=False)
            st.download_button(
                "📥 下载结果",
                data=output.getvalue(),
                file_name=f"查询结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_file"
            )
