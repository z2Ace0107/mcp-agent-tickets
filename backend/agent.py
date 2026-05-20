# -*- coding: utf-8 -*-
"""Agent 入口 — v5.0: AgentLoop 闭环执行"""

from typing import Any, AsyncGenerator

from backend.graph import run_graph, run_graph_stream
from backend.logger import get_logger

logger = get_logger(__name__)


async def run_agent(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """运行 Agent，返回最终结果。

    Returns:
        {"output": str, "intermediate_steps": [...], ...}
    """
    logger.info(f"[agent] 开始: '{user_input[:60]}...'")
    return await run_graph(user_input, chat_history)


async def run_agent_stream(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """流式运行 Agent，yield 进度事件 + 最终结果。

    Yields:
        {"type": "progress"|"token"|"done", ...}
    """
    async for event in run_graph_stream(user_input, chat_history):
        yield event
