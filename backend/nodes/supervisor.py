# -*- coding: utf-8 -*-
"""Supervisor 节点 — 意图分类 + 路由决策"""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from backend.prompts import SUPERVISOR_PROMPT
from backend.config import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)


def _create_llm(temperature: float = 0):
    from langchain_openai import ChatOpenAI
    settings = get_settings()
    return ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=temperature,
        max_tokens=256,
        extra_body={"thinking": {"type": "disabled"}},
    )


def supervisor_node(state: dict) -> dict:
    """分类用户意图，输出 intent + rewritten_query + route。

    路由映射:
        query → query_agent
        analyze → analyze_agent
        knowledge → knowledge_agent
        chat → reporter
    """
    user_input = state.get("user_input", "")
    chat_history = state.get("chat_history")

    history_text = "无"
    if chat_history:
        recent = chat_history[-4:]
        lines = [f"[{m.get('role', '?')}]: {m.get('content', '')[:200]}" for m in recent]
        history_text = "\n".join(lines)

    prompt = SUPERVISOR_PROMPT.format(history=history_text)

    try:
        llm = _create_llm()
        response = llm.invoke([
            SystemMessage(content="仅输出 JSON，不要其他内容。"),
            HumanMessage(content=f"用户输入: {user_input}\n\n{prompt}"),
        ])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)
        intent = result.get("intent", "chat")
        rewritten = result.get("rewritten_query", user_input)

        valid = {"query", "analyze", "knowledge", "chat"}
        if intent not in valid:
            intent = "chat"

        route_map = {
            "query": "query_agent",
            "analyze": "analyze_agent",
            "knowledge": "knowledge_agent",
            "chat": "reporter",
        }
        route = route_map[intent]

        logger.info(f"[supervisor] intent={intent} → {route}, q='{rewritten[:60]}...'")
    except Exception as e:
        logger.warning(f"[supervisor] 分类失败: {e}")
        intent = "chat"
        rewritten = user_input
        route = "reporter"

    return {
        "intent": intent,
        "rewritten_query": rewritten,
        "route": route,
        "active_agent": route,
    }
