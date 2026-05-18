# -*- coding: utf-8 -*-
"""Agent 入口 — v4.0: LineMind LangGraph 5-Agent 图"""

from typing import Any, AsyncGenerator

from backend.graph import run_graph, run_graph_stream
from backend.logger import get_logger

logger = get_logger(__name__)


async def run_agent(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
    max_retries: int = 3,
    max_iterations: int = 5,
) -> dict[str, Any]:
    """运行 LineMind LangGraph 图。

    Returns:
        {"output": str, "intermediate_steps": [...], "route": str, "intent": str, ...}
    """
    logger.info(f"[agent] 开始处理: '{user_input[:60]}...'")
    return await run_graph(user_input, chat_history)


async def run_agent_stream(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """v4.0: 流式运行 LineMind LangGraph 图，yield 节点进度 + 最终结果。

    Yields:
        {"type": "progress", "node": str, "label": str, ...}
        {"type": "done", "output": str, "intermediate_steps": [...], ...}
    """
    async for event in run_graph_stream(user_input, chat_history):
        yield event


def format_intermediate_steps(steps: list[dict[str, str]]) -> list[dict[str, str]]:
    return steps
