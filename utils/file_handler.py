"""
Excel/CSV 文件读写工具。
"""
import pandas as pd
from pathlib import Path


def read_table(path: str, id_column: str = "单号") -> pd.DataFrame:
    """读取表格文件，自动检测编码。

    :param path: 文件路径 (.xlsx/.xls/.csv)
    :param id_column: 预期的单号列名
    :return: DataFrame
    :raises FileNotFoundError: 文件不存在
    :raises ValueError: 格式不支持或列名无效
    """
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    suffix = filepath.suffix.lower()

    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    elif suffix == ".csv":
        df = None
        for enc in ["utf-8", "gbk", "gb2312", "gb18030", "latin-1"]:
            try:
                df = pd.read_csv(path, encoding=enc)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        if df is None:
            raise ValueError("无法识别 CSV 文件编码")
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")

    if id_column not in df.columns:
        available = ", ".join(df.columns.tolist())
        raise ValueError(f"列 '{id_column}' 不存在。可用列: {available}")

    return df


def write_table(df: pd.DataFrame, path: str):
    """写入表格文件。

    :param df: DataFrame
    :param path: 输出路径，根据后缀自动选择格式
    """
    suffix = Path(path).suffix.lower()
    if suffix in (".xlsx", ".xls"):
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")
