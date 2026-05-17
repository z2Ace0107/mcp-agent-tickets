# -*- coding: utf-8 -*-
"""LineMind — 制造业多智能体协管平台"""


def init_app() -> None:
    """初始化应用：加载配置、设置日志、初始化数据库、构建RAG索引。"""
    from backend.config import get_settings
    from backend.logger import setup_logging, get_logger
    from backend.database import init_db

    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    logger = get_logger(__name__)
    logger.info("正在初始化应用...")
    init_db(settings.DATABASE_PATH)

    # 构建 RAG 索引
    try:
        from backend.rag import index_solved_tickets
        count = index_solved_tickets()
        logger.info(f"RAG 索引构建完成，共 {count} 条已解决工单")
    except Exception as e:
        logger.warning(f"RAG 索引构建失败（可忽略，不影响核心功能）: {str(e)}")

    logger.info("应用初始化完成")
