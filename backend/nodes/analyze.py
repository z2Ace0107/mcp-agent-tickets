# -*- coding: utf-8 -*-
"""Analyze Agent 节点 — 统计分析 + 智能推荐（3 工具）"""

from langchain_core.messages import HumanMessage, SystemMessage

from backend.prompts import ANALYZE_AGENT_PROMPT
from backend.config import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)


def _create_llm():
    from langchain_openai import ChatOpenAI
    settings = get_settings()
    return ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=True,
        extra_body={"thinking": {"type": "disabled"}},
    )


def analyze_node(state: dict) -> dict:
    """Analyze Agent: 绑 3 工具做统计分析和推荐。"""
    from backend.graph import ANALYZE_TOOLS

    llm = _create_llm()
    llm_with_tools = llm.bind_tools(ANALYZE_TOOLS)

    messages = state.get("messages", [])
    rewritten = state.get("rewritten_query", state["user_input"])

    if not messages:
        messages = [
            SystemMessage(content=ANALYZE_AGENT_PROMPT),
            HumanMessage(content=rewritten),
        ]

    from backend.graph import strip_reasoning_content
    strip_reasoning_content(messages)
    logger.info("[analyze] 调用 LLM...")
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}
