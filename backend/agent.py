# -*- coding: utf-8 -*-
"""Agent核心逻辑 — llm.bind_tools() 手动工具调用循环"""

import json
import os
from datetime import datetime
from typing import Any

from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

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
_TOOL_MAP = {t.name: t for t in TOOLS}

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
# 系统提示词
# ============================================================

def _build_system_prompt() -> str:
    """构建带当前日期的系统提示词。"""
    current_date = datetime.now().strftime("%Y年%m月%d日")
    return SYSTEM_PROMPT.format(current_date=current_date)

# ============================================================
# 运行时逻辑
# ============================================================

async def run_agent(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
    max_retries: int = 3,
    max_iterations: int = 5,
) -> dict[str, Any]:
    """执行 Agent —— 使用 llm.bind_tools() 手动工具调用循环。

    Args:
        user_input: 用户输入的自然语言文本。
        chat_history: 历史对话记录，格式为 [{"role": "user/assistant", "content": "..."}, ...]。
        max_retries: 网络错误最大重试次数，默认 3 次。
        max_iterations: 工具调用最大轮数，默认 5 次。

    Returns:
        {"output": str, "intermediate_steps": [{"thought": ..., "action": ..., "action_input": ..., "observation": ...}, ...]}
    """
    llm = _create_llm()
    llm_with_tools = llm.bind_tools(TOOLS)

    messages = _build_initial_messages(user_input, chat_history)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            # 工具调用循环
            for _ in range(max_iterations):
                response = llm_with_tools.invoke(messages)
                messages.append(response)

                if response.tool_calls:
                    for tc in response.tool_calls:
                        tool_name = tc.get("name", "")
                        tool_args = tc.get("args", {})
                        tool_call_id = tc.get("id", "")
                        observation = _execute_tool(tool_name, tool_args)
                        messages.append(ToolMessage(
                            content=observation,
                            tool_call_id=tool_call_id,
                        ))
                else:
                    # 无工具调用，对话结束
                    break

            output = _clean_output(response.content)
            intermediate_steps = _extract_intermediate_steps(messages)
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


def _build_initial_messages(
    user_input: str,
    chat_history: list[dict[str, str]] | None,
) -> list:
    """构建初始消息列表（系统提示词 + 历史 + 当前问题）。"""
    messages = [SystemMessage(content=_build_system_prompt())]

    if chat_history:
        for entry in chat_history[-10:]:
            role = entry.get("role", "")
            content = entry.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_input))
    return messages


def _execute_tool(tool_name: str, tool_args: dict) -> str:
    """执行指定工具并返回结果字符串。"""
    tool_func = _TOOL_MAP.get(tool_name)
    if tool_func is None:
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
    try:
        result = tool_func.invoke(tool_args)
        return str(result)
    except Exception as e:
        return json.dumps({"error": f"工具执行失败: {str(e)}"}, ensure_ascii=False)


def _extract_intermediate_steps(messages: list) -> list[dict[str, str]]:
    """从消息列表中提取 ReAct 中间推理步骤。

    遍历消息列表，配对 AIMessage（含 tool_calls）与后续 ToolMessage，
    组成 Thought → Action → Action Input → Observation 链条。
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
                    "thought": str(msg.content)[:1000] if msg.content else f"调用 {tool_name}",
                    "action": tool_name,
                    "action_input": json.dumps(tool_args, ensure_ascii=False),
                    "observation": observation,
                })
    return steps


def _clean_output(output: str) -> str:
    """清洗输出：去除 ReAct 标记行。"""
    markers = ("Thought:", "Action:", "Action Input:", "Observation:", "Final Answer:")
    lines = output.split("\n")
    clean_lines = [l for l in lines if not any(l.strip().startswith(m) for m in markers)]
    cleaned = "\n".join(clean_lines).strip()
    return cleaned if cleaned else output


# ============================================================
# 中间步骤格式化（供前端展示）
# ============================================================

def format_intermediate_steps(
    steps: list[dict[str, str]],
) -> list[dict[str, str]]:
    """已格式化的中间步骤直接透传（兼容旧调用方）。"""
    return steps
