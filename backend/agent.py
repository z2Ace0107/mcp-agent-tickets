# -*- coding: utf-8 -*-
"""Agent核心逻辑 — llm.bind_tools() 手动工具调用循环"""

import json
import os
import time
from datetime import datetime
from typing import Any

from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from backend.tools import (
    query_tickets,
    analyze_tickets,
    update_ticket_status,
    assign_ticket,
    add_ticket_reply,
    get_ticket_detail,
    search_solutions,
    recommend_tickets,
    web_search,
)
from backend.prompts import SYSTEM_PROMPT
from backend.config import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)

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


@tool
def update_ticket_status_tool(ticket_id: str, new_status: str) -> str:
    """更新工单状态。ticket_id: 工单编号，必填; new_status: 新状态，必填，可选值：待处理/处理中/已解决/已关闭。"""
    result = update_ticket_status(ticket_id=ticket_id, new_status=new_status)
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def assign_ticket_tool(ticket_id: str, assignee: str) -> str:
    """分配工单给处理人。ticket_id: 工单编号，必填; assignee: 处理人姓名，必填。"""
    result = assign_ticket(ticket_id=ticket_id, assignee=assignee)
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def add_ticket_reply_tool(ticket_id: str, content: str) -> str:
    """为工单添加回复记录。ticket_id: 工单编号，必填; content: 回复内容，必填。"""
    result = add_ticket_reply(ticket_id=ticket_id, content=content)
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def get_ticket_detail_tool(ticket_id: str) -> str:
    """获取工单详情（包含所有回复记录）。ticket_id: 工单编号，必填。"""
    result = get_ticket_detail(ticket_id=ticket_id)
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def search_solutions_tool(query: str) -> str:
    """搜索历史已解决工单中类似问题的解决方案。当用户描述一个问题或故障时，使用此工具检索历史案例。query: 问题描述文本，必填。"""
    result = search_solutions(query=query)
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def recommend_tickets_tool() -> str:
    """智能推荐分析。分析当前工单状态，返回紧急未分配工单（含建议处理人）、积压预警、处理人工作量分布、关联工单群组、以及具体操作建议。当用户询问"建议"、"推荐"、"优先级"、"怎么处理"、"分配建议"时调用。无需参数。"""
    result = recommend_tickets()
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def web_search_tool(query: str) -> str:
    """联网搜索互联网获取实时信息。当用户询问的信息超出工单系统范围、需要最新资讯、产品或技术问题需要查外部资料时调用。query: 搜索关键词，必填。"""
    result = web_search(query=query)
    return json.dumps(result, ensure_ascii=False, indent=2)


TOOLS = [
    query_tickets_tool,
    analyze_tickets_tool,
    update_ticket_status_tool,
    assign_ticket_tool,
    add_ticket_reply_tool,
    get_ticket_detail_tool,
    search_solutions_tool,
    recommend_tickets_tool,
    web_search_tool,
]
_TOOL_MAP = {t.name: t for t in TOOLS}

# ============================================================
# LLM 初始化
# ============================================================

def _create_llm() -> ChatOpenAI:
    """创建 DeepSeek LLM 实例（兼容 OpenAI API 格式）。"""
    settings = get_settings()
    # api_key 从 os.environ 实时读取，因为 Streamlit 侧边栏可能在运行时动态设置
    api_key = os.environ.get("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY
    if not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY 未设置。请在 Streamlit 侧边栏输入，"
            "或在 .env 文件中设置 DEEPSEEK_API_KEY=your-key，"
            "或设置环境变量 DEEPSEEK_API_KEY。"
        )
    return ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=api_key,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        extra_body={"thinking": {"type": "disabled"}},
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
        logger.warning(f"未知工具调用: {tool_name}")
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
    try:
        logger.info(f"执行工具: {tool_name}, 参数: {tool_args}")
        start = time.time()
        result = tool_func.invoke(tool_args)
        elapsed = time.time() - start
        logger.info(f"工具 {tool_name} 执行完成，耗时 {elapsed:.2f}s")
        return str(result)
    except Exception as e:
        logger.error(f"工具 {tool_name} 执行失败: {str(e)}")
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
