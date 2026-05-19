# -*- coding: utf-8 -*-
"""Supervisor 节点 — 意图分类 + 路由决策 (v5.0: chat 直接回复)"""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.prompts import SUPERVISOR_PROMPT
from backend.config import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)

# 快捷问候关键词
CHAT_KEYWORDS = [
    "你好", "hello", "hi", "谢谢", "再见", "bye", "你是谁", "你能做什么",
    "有什么功能", "帮帮我", "怎么用", "早上好", "下午好", "晚上好",
]

CHAT_REPLY = (
    "你好！我是 LineMind 智能工单助手。\n\n"
    "可以帮你：\n"
    "- 📋 查询和筛选工单\n"
    "- 📊 分析工单趋势和分布\n"
    "- 🔍 搜索历史解决方案\n"
    "- 📝 更新工单状态/分配处理人\n\n"
    "直接输入问题即可，例如「最近一周有哪些设备故障工单」。"
)


def _create_llm(temperature: float = 0):
    from langchain_openai import ChatOpenAI
    settings = get_settings()
    return ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=temperature,
        max_tokens=256,
        streaming=True,
        extra_body={"thinking": {"type": "disabled"}},
    )


def _chat_reply(intent: str, rewritten: str, user_input: str) -> dict:
    """chat 意图——生成直接回复，不调用业务 Agent。"""
    return {
        "intent": "chat",
        "rewritten_query": rewritten,
        "route": "END",
        "active_agent": "",
        "messages": [AIMessage(content=CHAT_REPLY)],
    }


def supervisor_node(state: dict) -> dict:
    """分类用户意图，输出 intent + rewritten_query + route。"""
    user_input = state.get("user_input", "")
    chat_history = state.get("chat_history")

    # 快捷拦截：纯问候/闲聊直接返回
    stripped = user_input.strip().lower()
    if any(stripped.startswith(kw) or stripped == kw for kw in CHAT_KEYWORDS):
        return _chat_reply("chat", user_input, user_input)

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

        if intent == "chat":
            return _chat_reply(intent, rewritten, user_input)

        route_map = {
            "query": "query_agent",
            "analyze": "analyze_agent",
            "knowledge": "knowledge_agent",
        }
        route = route_map[intent]

        logger.info(f"[supervisor] intent={intent} → {route}, q='{rewritten[:60]}...'")
    except Exception as e:
        logger.warning(f"[supervisor] 分类失败: {e}")
        return _chat_reply("chat", user_input, user_input)

    return {
        "intent": intent,
        "rewritten_query": rewritten,
        "route": route,
        "active_agent": route,
    }
