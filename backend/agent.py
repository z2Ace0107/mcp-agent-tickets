# -*- coding: utf-8 -*-
"""Agent核心逻辑 — v3.0: 预处理路由 + 安全防护 + 证据预算 + 混合记忆"""

import asyncio
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as ThreadTimeoutError
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
from backend.prompts import SYSTEM_PROMPT, PREPROCESS_PROMPT, CHAT_SYSTEM_PROMPT
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
# v3.0 常量
# ============================================================

TOOL_TIMEOUT = 10
CIRCUIT_BREAKER_THRESHOLD = 3
RETRY_BACKOFFS = [0.2, 0.4, 0.8]

EVIDENCE_LIMITS = {
    "search_solutions_tool": 1500,
    "query_tickets_tool": 2000,
    "web_search_tool": 1200,
}
DEFAULT_EVIDENCE_LIMIT = 2500
TOTAL_EVIDENCE_BUDGET = 5200

RECENT_WINDOW = 4
MAX_HISTORY = 10

# ============================================================
# LLM 初始化
# ============================================================

def _create_llm(temperature: float | None = None) -> ChatOpenAI:
    """创建 DeepSeek LLM 实例（兼容 OpenAI API 格式）。"""
    settings = get_settings()
    api_key = os.environ.get("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY
    if not api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY 未设置。请在 Streamlit 侧边栏输入，"
            "或在 .env 文件中设置 DEEPSEEK_API_KEY=your-key，"
            "或设置环境变量 DEEPSEEK_API_KEY。"
        )
    temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
    return ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=api_key,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=temp,
        max_tokens=settings.LLM_MAX_TOKENS,
        extra_body={"thinking": {"type": "disabled"}},
    )


def _build_system_prompt() -> str:
    current_date = datetime.now().strftime("%Y年%m月%d日")
    return SYSTEM_PROMPT.format(current_date=current_date)

# ============================================================
# v3.3 证据预算 — 工具结果裁剪
# ============================================================

def _trim_tool_result(tool_name: str, result_str: str) -> tuple[str, int, bool]:
    """按工具类型裁剪输出。返回 (裁剪后文本, 原始长度, 是否被裁剪)。"""
    limit = EVIDENCE_LIMITS.get(tool_name, DEFAULT_EVIDENCE_LIMIT)
    original_len = len(result_str)
    if original_len <= limit:
        return result_str, original_len, False
    trimmed = result_str[:limit] + f"\n\n...(共 {original_len} 字符，已裁剪至 {limit} 字符)"
    logger.info(f"工具 {tool_name} 输出已裁剪: {original_len} → {limit} 字符")
    return trimmed, original_len, True


def _total_evidence_check(accumulated: int) -> bool:
    if accumulated > TOTAL_EVIDENCE_BUDGET * 0.8:
        logger.warning(f"证据累积 {accumulated} 字符，接近预算上限 {TOTAL_EVIDENCE_BUDGET}")
    return accumulated >= TOTAL_EVIDENCE_BUDGET

# ============================================================
# v3.2 安全防护 — 工具执行增强
# ============================================================

def _execute_tool(
    tool_name: str,
    tool_args: dict,
    circuit_state: dict[str, int] | None = None,
) -> tuple[str, dict]:
    """执行指定工具，返回 (结果字符串, 执行元信息)。

    元信息字段: elapsed, original_length, trimmed, degraded, retries
    """
    meta = {"elapsed": 0.0, "original_length": 0, "trimmed": False, "degraded": False, "retries": 0}

    # 熔断器检查
    if circuit_state is not None:
        failures = circuit_state.get(tool_name, 0)
        if failures >= CIRCUIT_BREAKER_THRESHOLD:
            logger.warning(f"工具 {tool_name} 已熔断（连续失败 {failures} 次），本轮跳过")
            meta["degraded"] = True
            return json.dumps({
                "error": f"工具 {tool_name} 暂时不可用（已熔断）",
                "degraded": True,
            }, ensure_ascii=False), meta

    tool_func = _TOOL_MAP.get(tool_name)
    if tool_func is None:
        logger.warning(f"未知工具调用: {tool_name}")
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False), meta

    last_error = None
    for attempt in range(len(RETRY_BACKOFFS) + 1):
        try:
            logger.info(f"执行工具: {tool_name}, 参数: {tool_args}, 尝试: {attempt + 1}")
            start = time.time()

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(tool_func.invoke, tool_args)
                result = future.result(timeout=TOOL_TIMEOUT)

            meta["elapsed"] = round(time.time() - start, 3)
            meta["retries"] = attempt

            if circuit_state is not None:
                circuit_state[tool_name] = 0

            trimmed_result, orig_len, was_trimmed = _trim_tool_result(tool_name, str(result))
            meta["original_length"] = orig_len
            meta["trimmed"] = was_trimmed
            logger.info(f"工具 {tool_name} 完成，耗时 {meta['elapsed']}s，原始 {orig_len} 字符")
            return trimmed_result, meta

        except ThreadTimeoutError:
            last_error = f"工具 {tool_name} 执行超时（{TOOL_TIMEOUT}s）"
            logger.warning(last_error)
        except Exception as e:
            last_error = str(e)
            logger.warning(f"工具 {tool_name} 执行失败（尝试 {attempt + 1}）: {last_error}")

        if attempt < len(RETRY_BACKOFFS):
            backoff = RETRY_BACKOFFS[attempt]
            logger.info(f"工具 {tool_name} 等待 {backoff}s 后重试...")
            time.sleep(backoff)

    # 全部重试失败 → 更新熔断器
    if circuit_state is not None:
        circuit_state[tool_name] = circuit_state.get(tool_name, 0) + 1
        logger.error(
            f"工具 {tool_name} 连续失败 {circuit_state[tool_name]} 次"
        )

    meta["degraded"] = True
    meta["retries"] = len(RETRY_BACKOFFS)
    return json.dumps({
        "error": "工具执行失败，已降级处理",
        "detail": str(last_error)[:200],
        "degraded": True,
    }, ensure_ascii=False), meta

# ============================================================
# v3.4 会话记忆 — 摘要压缩
# ============================================================

async def _compress_history(
    chat_history: list[dict[str, str]],
    keep_recent: int = RECENT_WINDOW,
) -> tuple[str | None, dict]:
    """将早期消息压缩为摘要文本。返回 (摘要, 压缩信息)。"""
    info = {"total_messages": len(chat_history), "compressed": 0, "kept": 0}
    early = chat_history[:-keep_recent] if len(chat_history) > keep_recent else []
    if not early:
        info["kept"] = len(chat_history)
        return None, info

    info["compressed"] = len(early)
    info["kept"] = keep_recent

    try:
        llm = _create_llm(temperature=0)
        history_text = "\n".join(
            f"[{m.get('role', '?')}]: {m.get('content', '')[:300]}" for m in early
        )
        prompt = (
            "请用 2-3 句话总结以下对话历史，保留关键信息（工单编号、日期、操作结果等）：\n\n"
            + history_text
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        summary = response.content.strip()
        logger.info(f"对话摘要压缩: {len(early)} → {len(summary)} 字符")
        return summary, info
    except Exception as e:
        logger.warning(f"对话摘要压缩失败: {e}")
        return None, info


def _build_initial_messages(
    user_input: str,
    chat_history: list[dict[str, str]] | None,
    history_summary: str | None = None,
) -> list:
    """构建初始消息列表 — v3.0 混合记忆策略。"""
    messages = [SystemMessage(content=_build_system_prompt())]

    if history_summary:
        messages.append(SystemMessage(
            content=f"[早期对话摘要] {history_summary}"
        ))

    if chat_history:
        recent = chat_history[-MAX_HISTORY:]
        for entry in recent:
            role = entry.get("role", "")
            content = entry.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_input))
    return messages

# ============================================================
# v3.1 预处理 + 路由
# ============================================================

async def _preprocess(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    """单次 LLM 调用完成意图分类、问题改写和路由决策。"""
    history_text = "无"
    if chat_history:
        recent = chat_history[-4:]
        lines = [
            f"[{m.get('role', '?')}]: {m.get('content', '')[:200]}"
            for m in recent
        ]
        history_text = "\n".join(lines)

    prompt = PREPROCESS_PROMPT.format(history=history_text)

    try:
        llm = _create_llm(temperature=0)
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
        route = result.get("route", "complex")

        valid_intents = {"query", "analyze", "recommend", "search", "chat"}
        valid_routes = {"chat", "simple_query", "complex"}
        if intent not in valid_intents:
            intent = "chat"
        if route not in valid_routes:
            route = "complex"

        logger.info(f"预处理: intent={intent}, route={route}, q='{rewritten[:60]}...'")
        return {"intent": intent, "rewritten_query": rewritten, "route": route}

    except Exception as e:
        logger.warning(f"预处理失败，退避到完整 Agent 循环: {e}")
        return {"intent": "unknown", "rewritten_query": user_input, "route": "complex"}


async def _chat_directly(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """chat 路由：直接对话，不走工具调用。"""
    try:
        llm = _create_llm(temperature=0.1)
        messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT)]
        if chat_history:
            for entry in chat_history[-4:]:
                role = entry.get("role", "")
                content = entry.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=user_input))
        response = llm.invoke(messages)
        return {"output": response.content.strip(), "intermediate_steps": []}
    except Exception as e:
        return {"output": f"抱歉，出了点问题：{e}", "intermediate_steps": []}

# ============================================================
# 运行时逻辑
# ============================================================

async def run_agent(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
    max_retries: int = 3,
    max_iterations: int = 5,
) -> dict[str, Any]:
    """v3.0: 预处理路由 → 安全工具调用 → 证据预算 → 混合记忆。

    Returns:
        {
            "output": str,
            "intermediate_steps": [...],
            "route": "chat"|"simple_query"|"complex",
            "intent": "query"|"analyze"|"recommend"|"search"|"chat",
            "rewritten_query": str,
            "context_info": {"total_messages": int, "compressed": int, "kept": int} | None,
        }
    """

    # ---- v3.1 预处理路由 ----
    pre = await _preprocess(user_input, chat_history)
    route = pre["route"]
    intent = pre["intent"]
    rewritten = pre["rewritten_query"]

    if route == "chat":
        logger.info(f"路由 → chat: '{rewritten[:60]}...'")
        result = await _chat_directly(rewritten, chat_history)
        result["route"] = route
        result["intent"] = intent
        result["rewritten_query"] = rewritten
        result["context_info"] = None
        return result

    # ---- v3.4 历史压缩 ----
    history_summary = None
    context_info = None
    if chat_history and len(chat_history) > MAX_HISTORY:
        history_summary, context_info = await _compress_history(chat_history)
    elif chat_history:
        context_info = {"total_messages": len(chat_history), "compressed": 0, "kept": len(chat_history)}

    # ---- 初始化 ----
    llm = _create_llm()
    llm_with_tools = llm.bind_tools(TOOLS)
    messages = _build_initial_messages(rewritten, chat_history, history_summary)
    circuit_state: dict[str, int] = {}
    tool_meta: dict[str, dict] = {}  # tool_call_id → 元信息

    max_iter = 2 if route == "simple_query" else max_iterations  # 1次工具调用 + 1次生成回答
    evidence_accumulated = 0

    # ---- 工具调用循环 ----
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            for iteration in range(max_iter):
                if _total_evidence_check(evidence_accumulated):
                    messages.append(SystemMessage(
                        content="工具返回数据已接近上限，请基于已有信息直接回复，不要再调用工具。"
                    ))

                response = llm_with_tools.invoke(messages)
                messages.append(response)

                if response.tool_calls:
                    for tc in response.tool_calls:
                        tool_name = tc.get("name", "")
                        tool_args = tc.get("args", {})
                        tool_call_id = tc.get("id", "")

                        observation, tmeta = _execute_tool(tool_name, tool_args, circuit_state)
                        tool_meta[tool_call_id] = tmeta
                        evidence_accumulated += len(observation)

                        messages.append(ToolMessage(
                            content=observation,
                            tool_call_id=tool_call_id,
                        ))
                else:
                    break

            output = _clean_output(response.content)
            steps = _extract_intermediate_steps(messages, tool_meta)
            return {
                "output": output,
                "intermediate_steps": steps,
                "route": route,
                "intent": intent,
                "rewritten_query": rewritten,
                "context_info": context_info,
            }

        except Exception as e:
            last_error = e
            logger.error(f"Agent 执行异常（尝试 {attempt + 1}）: {e}")
            if attempt < max_retries:
                continue
            break

    return {
        "output": f"抱歉，Agent 经过 {max_retries} 次重试后仍无法处理您的请求。错误信息：{str(last_error)}",
        "intermediate_steps": [],
        "route": route,
        "intent": intent,
        "rewritten_query": rewritten,
        "context_info": context_info,
    }


def _extract_intermediate_steps(
    messages: list,
    tool_meta: dict[str, dict] | None = None,
) -> list[dict[str, Any]]:
    """从消息列表中提取 ReAct 中间推理步骤（含工具执行元信息）。"""
    if tool_meta is None:
        tool_meta = {}
    steps = []
    for i, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.get("name", "unknown")
                tool_args = tc.get("args", {})
                tool_call_id = tc.get("id", "")

                observation = ""
                for j in range(i + 1, len(messages)):
                    candidate = messages[j]
                    if isinstance(candidate, ToolMessage) and getattr(candidate, "tool_call_id", "") == tool_call_id:
                        observation = str(candidate.content)[:2000]
                        break

                meta = tool_meta.get(tool_call_id, {})
                steps.append({
                    "thought": str(msg.content)[:1000] if msg.content else f"调用 {tool_name}",
                    "action": tool_name,
                    "action_input": json.dumps(tool_args, ensure_ascii=False),
                    "observation": observation,
                    "elapsed": meta.get("elapsed", 0),
                    "original_length": meta.get("original_length", 0),
                    "trimmed": meta.get("trimmed", False),
                    "degraded": meta.get("degraded", False),
                    "retries": meta.get("retries", 0),
                })
    return steps


def _clean_output(output: str) -> str:
    markers = ("Thought:", "Action:", "Action Input:", "Observation:", "Final Answer:")
    lines = output.split("\n")
    clean_lines = [l for l in lines if not any(l.strip().startswith(m) for m in markers)]
    cleaned = "\n".join(clean_lines).strip()
    return cleaned if cleaned else output


def format_intermediate_steps(
    steps: list[dict[str, str]],
) -> list[dict[str, str]]:
    return steps
