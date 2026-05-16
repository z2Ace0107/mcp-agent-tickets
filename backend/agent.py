# -*- coding: utf-8 -*-
"""Agent 入口 — v3.3: LangGraph 5-Agent 图"""

from typing import Any

from backend.graph import run_graph
from backend.logger import get_logger

logger = get_logger(__name__)


async def run_agent(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
    max_retries: int = 3,
    max_iterations: int = 5,
) -> dict[str, Any]:
    """运行 LangGraph Super Agent。

    Returns:
        {"output": str, "intermediate_steps": [...], "route": str, "intent": str, ...}
    """
    logger.info(f"[agent] 开始处理: '{user_input[:60]}...'")
    return await run_graph(user_input, chat_history)


def format_intermediate_steps(steps: list[dict[str, str]]) -> list[dict[str, str]]:
    return steps
