# -*- coding: utf-8 -*-
"""日志配置 — Python logging 模块封装"""

import logging
import os
import sys

_logging_initialized = False


def setup_logging(level: str = "INFO") -> None:
    """初始化日志系统，同时输出到控制台和文件。多次调用安全（幂等）。

    Args:
        level: 日志级别字符串，可选 DEBUG/INFO/WARNING/ERROR。
    """
    global _logging_initialized
    if _logging_initialized:
        return

    log_format = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 解析日志级别
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # 根 logger 配置
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(console_handler)

    # 文件 handler（可选）
    from backend.config import get_settings
    settings = get_settings()
    log_dir = os.path.dirname(settings.LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.FileHandler(settings.LOG_FILE, encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(file_handler)

    _logging_initialized = True


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger。

    Args:
        name: logger 名称，通常传 __name__。

    Returns:
        logging.Logger 实例。
    """
    return logging.getLogger(name)
