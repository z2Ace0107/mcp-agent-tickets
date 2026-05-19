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
    """Reporter: 绑 REPORTER_TOOLS，LLM 决定是否调 execute_python 画图。
    工具调用回 tool_executor_node 统一执行，消除双路径。
    """
    from backend.graph import REPORTER_TOOLS, MAX_AGENT_ITERATIONS

    llm = _create_llm()
    # 仅在首轮绑定工具（后续迭代由 agent_iterations 控制）
    agent_iterations = state.get("agent_iterations", 0)
    if agent_iterations < MAX_AGENT_ITERATIONS - 1:
        llm = llm.bind_tools(REPORTER_TOOLS)

    messages = state.get("messages", [])
    user_input = state.get("rewritten_query", state["user_input"])

    if not messages:
        current_date = datetime.now().strftime("%Y年%m月%d日")
        system = SystemMessage(content=REPORTER_PROMPT.format(current_date=current_date))
        messages = [system, HumanMessage(content=user_input)]

    from backend.graph import strip_reasoning_content
    strip_reasoning_content(messages)
    logger.info("[reporter] 生成回复..." + (" (含工具)" if agent_iterations < MAX_AGENT_ITERATIONS - 1 else " (终轮无工具)"))
    response = llm.invoke(messages)
    return {"messages": [response], "active_agent": "reporter"}
