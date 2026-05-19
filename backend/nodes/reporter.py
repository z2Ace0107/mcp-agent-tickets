# -*- coding: utf-8 -*-
"""Reporter 节点 — 聚合上游结果 + 格式化最终回复（v4.0: 工具走 tool_executor）"""

from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from backend.prompts import REPORTER_PROMPT
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


def reporter_node(state: dict) -> dict:
    """Reporter: 汇总对话历史 + 格式化最终回复。不绑定任何工具。"""

    llm = _create_llm()
    # Reporter 永不绑工具，避免 LLM 模仿历史消息里的 tool_calls
    llm = llm.bind_tools([], tool_choice="none")

    messages = state.get("messages", [])
    user_input = state.get("rewritten_query", state["user_input"])
    current_date = datetime.now().strftime("%Y年%m月%d日")
    system = SystemMessage(content=REPORTER_PROMPT.format(current_date=current_date))
    if not messages:
        messages = [system, HumanMessage(content=user_input)]
    else:
        messages = [system] + list(messages)

    from backend.graph import strip_reasoning_content
    strip_reasoning_content(messages)
    logger.info("[reporter] 生成回复...")
    response = llm.invoke(messages)
    return {"messages": [response], "active_agent": "reporter"}
