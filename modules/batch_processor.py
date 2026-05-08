"""
模块 D: 批量表格处理。

读取 Excel/CSV 文件，逐条查询订单地址，输出带结果的文件。
"""
import asyncio
import logging
import random
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page

from .address_viewer import get_full_address
from .order_search import classify_order

logger = logging.getLogger(__name__)


async def process_batch(
    page: Page,
    input_path: str,
    output_path: str,
    id_column: str = "单号",
    query_interval: float = 2.0,
) -> dict:
    """
    批量处理表格文件中的订单单号。

    :param page: Playwright Page 对象
    :param input_path: 输入文件路径 (.xlsx/.xls/.csv)
    :param output_path: 输出文件路径
    :param id_column: 单号列名，默认 "单号"
    :param query_interval: 查询间隔秒数，默认 2 秒
    :return: 处理结果统计
    """
    import pandas as pd

    # 读取文件
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(input_path)
    elif path.suffix.lower() == ".csv":
        # 自动检测编码
        for enc in ["utf-8", "gbk", "gb2312", "gb18030"]:
            try:
                df = pd.read_csv(input_path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("无法识别 CSV 编码")
    else:
        raise ValueError(f"不支持的文件格式: {path.suffix}")

    # 查找单号列
    if id_column not in df.columns:
        available = ", ".join(df.columns.tolist())
        raise ValueError(f"列 '{id_column}' 不存在。可用列: {available}")

    # 清理单号
    df[id_column] = df[id_column].astype(str).str.strip()

    # 新增结果列
    result_column = "查询地址"
    df[result_column] = ""

    total = len(df)
    success = 0
    failed = 0
    skipped = 0

    logger.info("开始批量处理: 共 %d 条记录", total)

    for idx, row in df.iterrows():
        order_id = row[id_column]
        if not order_id or order_id == "nan":
            df.at[idx, result_column] = "ERROR: 空单号"
            skipped += 1
            continue

        # 验证单号格式
        order_type = classify_order(order_id)
        if order_type == "unknown":
            df.at[idx, result_column] = f"ERROR: 非法单号前缀 ({order_id})"
            skipped += 1
            logger.warning("[%d/%d] 跳过非法单号: %s", idx + 1, total, order_id)
            continue

        logger.info("[%d/%d] 查询: %s", idx + 1, total, order_id)

        # 获取地址
        address = await get_full_address(page, order_id)
        df.at[idx, result_column] = address

        if address and not address.startswith("ERROR"):
            success += 1
        else:
            failed += 1

        # 随机延时防止频率限制
        delay = query_interval + random.uniform(0, 1)
        await asyncio.sleep(delay)

    # 写入输出文件
    output = Path(output_path)
    if output.suffix.lower() in (".xlsx", ".xls"):
        df.to_excel(output_path, index=False)
    else:
        df.to_csv(output_path, index=False, encoding="utf-8-sig")

    result = {
        "total": total,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "output": str(output.absolute()),
    }
    logger.info("批量处理完成: %s", result)
    return result
