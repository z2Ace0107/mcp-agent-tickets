# -*- coding: utf-8 -*-
"""配置管理 — 从 .env 文件和环境变量加载配置"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 加载 .env 文件
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """应用配置，所有值优先从环境变量读取，其次使用默认值。"""

    # DeepSeek API（LLM 对话，直连）
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    # OpenCode Go API（优先使用，OpenAI 兼容代理）
    GO_API_KEY: str = os.getenv("GO_API_KEY", "")
    GO_BASE_URL: str = os.getenv("GO_BASE_URL", "https://opencode.ai/zen/go/v1")
    GO_MODEL: str = os.getenv("GO_MODEL", "deepseek-v4-flash")

    # 百度 AI 搜索 API（联网搜索）
    BAIDU_API_KEY: str = os.getenv("BAIDU_API_KEY", "")
    BAIDU_SEARCH_BASE_URL: str = os.getenv("BAIDU_SEARCH_BASE_URL", "https://qianfan.baidubce.com/v2/ai_search")

    # Embedding API（阿里云百炼，OpenAI 兼容）
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
    EMBEDDING_BASE_URL: str = os.getenv("EMBEDDING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # 数据库
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "tickets.db"))

    # ChromaDB
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", str(PROJECT_ROOT / "chroma_data"))

    # 日志
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", str(PROJECT_ROOT / "logs" / "agent.log"))

    # LLM 参数
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # Agent 参数
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "5"))

    # MCP Server (stdio transport, no HTTP port needed)


_settings: Settings | None = None


def get_settings() -> Settings:
    """获取 Settings 单例。"""
    global _settings
    if _settings is None:
        _settings = Settings()
        # 确保数据目录存在
        db_dir = os.path.dirname(_settings.DATABASE_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        chroma_dir = _settings.CHROMA_PERSIST_DIR
        if chroma_dir:
            os.makedirs(chroma_dir, exist_ok=True)
        log_dir = os.path.dirname(_settings.LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    return _settings
