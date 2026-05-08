# -*- coding: utf-8 -*-
"""Agent核心逻辑 — ReAct模式、工具调度、错误重试"""

import json
import os
from datetime import datetime
from typing import Any

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.tools import query_tickets, analyze_tickets
from backend.prompts import SYSTEM_PROMPT

# ============================================================
# 工具注册
# ============================================================

@tool
def query_tickets_tool(
    ticket_type: str | None = None,
    status: str | None = None,
    date_range: str | None = None,
) -> str:
    """按条件筛选工单列表。参数均为可选。ticket_type: 退款/技术/咨询/投诉; status: 待处理/处理中/已解决/已关闭; date_range: today/week/month/YYYY-MM-DD,YYYY-MM-DD。"""
    result = query_tickets(ticket_type=ticket_type, status=status, date_range=date_range)
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def analyze_tickets_tool(analysis_type: str) -> str:
    """对工单数据进行统计分析。analysis_type必填，可选: type_distribution/status_distribution/priority_distribution/trend/summary。"""
    result = analyze_tickets(analysis_type=analysis_type)
    return json.dumps(result, ensure_ascii=False, indent=2)


TOOLS = [query_tickets_tool, analyze_tickets_tool]

# ============================================================
# LLM 初始化
# ============================================================

def _create_llm() -> ChatOpenAI:
    """创建 DeepSeek LLM 实例（兼容 OpenAI API 格式）。"""
    return ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        temperature=0,
        max_tokens=4096,
    )

# ============================================================
# Agent 构建
# ============================================================

_agent_cache: Any = None


def _build_system_prompt() -> str:
    """构建带当前日期的系统提示词。"""
    current_date = datetime.now().strftime("%Y年%m月%d日")
    return SYSTEM_PROMPT.format(current_date=current_date)


def get_agent():
    """获取编译后的 Agent（懒加载单例）。"""
    global _agent_cache
    if _agent_cache is None:
        _agent_cache = create_agent(
            model=_create_llm(),
            tools=TOOLS,
            system_prompt=_build_system_prompt(),
        )
    return _agent_cache

# ============================================================
# 运行时逻辑
# ============================================================

async def run_agent(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """执行 Agent，支持解析错误自动重试。

    Args:
        user_input: 用户输入的自然语言文本。
        chat_history: 历史对话记录，格式为 [{"role": "user/assistant", "content": "..."}, ...]。
        max_retries: 解析错误最大重试次数，默认 3 次。

    Returns:
        {"output": str, "intermediate_steps": list[dict[str, str]]}
    """
    agent = get_agent()
    messages = _build_messages(user_input, chat_history)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = agent.invoke({"messages": messages})
            all_messages = result.get("messages", [])
            output = _extract_final_answer(all_messages)
            intermediate_steps = _extract_intermediate_steps(all_messages)
            return {
                "output": output,
                "intermediate_steps": intermediate_steps,
            }
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                continue
            break

    return {
        "output": f"抱歉，Agent 经过 {max_retries} 次重试后仍无法处理您的请求。错误信息：{str(last_error)}",
        "intermediate_steps": [],
    }


def _build_messages(
    user_input: str,
    chat_history: list[dict[str, str]] | None,
) -> list:
    """将用户输入和对话历史组装为 LangChain 消息列表。"""
    messages = []
    if chat_history:
        for entry in chat_history[-20:]:
            role = entry.get("role", "")
            content = entry.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_input))
    return messages


def _extract_final_answer(messages: list) -> str:
    """从消息列表中提取最终 AI 回复文本。"""
    # 倒序遍历，取最后一条 AIMessage 的 content（排除 tool_calls 的空回复）
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content and not m.tool_calls:
            return m.content
    # 兜底：取最后一条 AIMessage（可能带 tool_calls）
    for m in reversed(messages):
        if isinstance(m, AIMessage) and m.content:
            return m.content
    return "Agent 未生成回复。"


def _extract_intermediate_steps(messages: list) -> list[dict[str, str]]:
    """从消息列表中提取 ReAct 中间推理步骤。

    遍历消息列表，配对 AIMessage（含 tool_calls）与后续 ToolMessage，
    组成 Thought → Action → Observation 链条。
    """
    steps = []
    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.get("name", "unknown")
                tool_args = tc.get("args", {})
                tool_call_id = tc.get("id", "")

                # 查找对应的 ToolMessage
                observation = ""
                for j in range(i + 1, len(messages)):
                    candidate = messages[j]
                    if isinstance(candidate, ToolMessage) and getattr(candidate, "tool_call_id", "") == tool_call_id:
                        observation = str(candidate.content)[:2000]
                        break

                steps.append({
                    "thought": str(msg.content)[:1000] if msg.content else f"决定调用 {tool_name}",
                    "action": tool_name,
                    "action_input": json.dumps(tool_args, ensure_ascii=False),
                    "observation": observation,
                })
    return steps


# ============================================================
# 中间步骤格式化（供前端展示）
# ============================================================

def format_intermediate_steps(
    steps: list[dict[str, str]],
) -> list[dict[str, str]]:
    """已格式化的中间步骤直接透传（兼容旧调用方）。"""
    return steps
