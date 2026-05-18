# -*- coding: utf-8 -*-
"""Query Agent 节点 — 数据检索 + 工单操作（6 工具）"""

from langchain_core.messages import HumanMessage, SystemMessage

from backend.prompts import QUERY_AGENT_PROMPT
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


def query_node(state: dict) -> dict:
    """Query Agent: 绑 6 工具做数据检索和工单操作。"""
    from backend.graph import QUERY_TOOLS

    llm = _create_llm()
    llm_with_tools = llm.bind_tools(QUERY_TOOLS)

    messages = state.get("messages", [])
    rewritten = state.get("rewritten_query", state["user_input"])

    # 首次进入：注入 SystemMessage + HumanMessage
    if not messages:
        messages = [
            SystemMessage(content=QUERY_AGENT_PROMPT),
            HumanMessage(content=rewritten),
        ]

    logger.info("[query] 调用 LLM...")
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}
