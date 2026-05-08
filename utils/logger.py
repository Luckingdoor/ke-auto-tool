"""
日志配置。
"""
import logging
import sys
from datetime import datetime


def setup_logger(name: str = "ke_auto", level: int = logging.INFO) -> logging.Logger:
    """配置并返回 logger 实例。"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    return logger
