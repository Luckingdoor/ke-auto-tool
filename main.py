#!/usr/bin/env python3
"""
贝壳维修工作台自动化查询工具

Usage:
  # 单条查询
  python main.py --mode single --order-id S01002026050817809700252

  # 批量表格查询
  python main.py --mode batch --input ./orders.xlsx --output ./result.xlsx

  # 指定城市
  python main.py --mode single --order-id S0100... --city 杭州市

  # 无头模式
  python main.py --mode batch --input ./orders.xlsx --output ./result.xlsx --headless
"""
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from config import get_cookies, get_config
from browser import BrowserContext
from modules import (
    switch_city,
    get_full_address,
    process_batch,
)
from utils import setup_logger, classify_order

logger = setup_logger()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="贝壳维修工作台自动化查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--mode", choices=["single", "batch"], required=True, help="运行模式")
    p.add_argument("--order-id", help="单条查询时的单号 (mode=single 必填)")
    p.add_argument("--input", help="批量查询时的输入表格路径 (mode=batch 必填)")
    p.add_argument("--output", help="批量查询时的输出路径 (默认: 输入文件名_已查询_时间戳.xlsx)")
    p.add_argument("--city", help="目标城市，如 杭州市。不填则保持 Cookie 默认城市")
    p.add_argument("--cookie", help="Cookie 文件路径或 JSON 字符串")
    p.add_argument("--headless", action="store_true", help="无头模式（不显示浏览器窗口）")
    p.add_argument("--interval", type=float, default=2.0, help="查询间隔秒数 (默认 2)")
    return p


def validate_single(args, parser):
    if not args.order_id:
        parser.error("mode=single 需要 --order-id 参数")
    order_type = classify_order(args.order_id)
    if order_type == "INVALID":
        parser.error(f"无效单号前缀: {args.order_id}（需 S 或 T 开头）")


def validate_batch(args, parser):
    if not args.input:
        parser.error("mode=batch 需要 --input 参数")
    if not Path(args.input).exists():
        parser.error(f"输入文件不存在: {args.input}")
    if not args.output:
        stem = Path(args.input).stem
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"{stem}_已查询_{ts}.xlsx"


async def run_single(cookies: list[dict], args):
    """单条查询模式。"""
    config = get_config()
    headless = args.headless or config["headless"]
    city = args.city or config["city"]
    order_id = args.order_id

    logger.info("单条查询模式: %s", order_id)

    async with BrowserContext(cookies, headless=headless) as ctx:
        # 城市切换
        if city:
            logger.info("切换城市至: %s", city)
            ok = await switch_city(ctx.page, city)
            if not ok:
                logger.warning("城市切换失败，继续使用当前城市")

        # 获取地址
        address = await get_full_address(ctx.page, order_id)
        print(f"\n{'='*50}")
        print(f"单号:   {order_id}")
        print(f"地址:   {address}")
        print(f"{'='*50}\n")


async def run_batch(cookies: list[dict], args):
    """批量表格查询模式。"""
    config = get_config()
    headless = args.headless or config["headless"]
    city = args.city or config["city"]
    interval = args.interval or config["query_interval"]

    logger.info("批量查询模式: %s -> %s", args.input, args.output)

    async with BrowserContext(cookies, headless=headless) as ctx:
        if city:
            logger.info("切换城市至: %s", city)
            ok = await switch_city(ctx.page, city)
            if not ok:
                logger.warning("城市切换失败，继续使用当前城市")

        result = await process_batch(
            page=ctx.page,
            input_path=args.input,
            output_path=args.output,
            query_interval=interval,
        )

        print(f"\n{'='*50}")
        print(f"批量查询完成!")
        print(f"  总数:   {result['total']}")
        print(f"  成功:   {result['success']}")
        print(f"  失败:   {result['failed']}")
        print(f"  跳过:   {result['skipped']}")
        print(f"  输出:   {result['output']}")
        print(f"{'='*50}\n")


async def main():
    parser = build_parser()
    args = parser.parse_args()

    # 参数校验
    if args.mode == "single":
        validate_single(args, parser)
    elif args.mode == "batch":
        validate_batch(args, parser)

    # 加载 Cookie
    city = args.city or get_config().get("city")
    try:
        if args.cookie:
            from browser.login import parse_cookie_string, load_cookie_from_file

            path = Path(args.cookie)
            if path.exists():
                cookies = load_cookie_from_file(str(path), city=city)
            else:
                cookies = parse_cookie_string(args.cookie)
            if not cookies:
                print("错误: 无法解析 Cookie")
                sys.exit(1)
        else:
            cookies = get_cookies()
    except Exception as e:
        print(f"错误: Cookie 加载失败 - {e}")
        sys.exit(1)

    logger.info("Cookie 加载成功: %d 条", len(cookies))

    # 执行
    try:
        if args.mode == "single":
            await run_single(cookies, args)
        else:
            await run_batch(cookies, args)
    except RuntimeError as e:
        logger.error("运行失败: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.exception("未知错误: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
