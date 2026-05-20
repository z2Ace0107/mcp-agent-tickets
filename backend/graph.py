# -*- coding: utf-8 -*-
"""v5.0 Agent Loop 图 — AgentLoop 自循环 + LangGraph 薄壳（状态管理 + 流式输出）"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as ThreadTimeoutError
from typing import Any

from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage

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
    get_schema,
    execute_sql,
    execute_python,
)
from backend.agent_loop import AgentLoop
from backend.config import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)


# ============================================================
# 12 个 LangChain 工具
# ============================================================

@tool
def query_tickets_tool(
    ticket_type: str | None = None,
    status: str | None = None,
    date_range: str | None = None,
    priority: str | None = None,
) -> str:
    """按条件筛选工单列表。参数均为可选。ticket_type: 设备故障/质量异常/安全隐患/物料短缺/工艺问题/生产计划/环境监测; status: 待处理/处理中/已解决/已关闭; date_range: today/week/month/YYYY-MM-DD,YYYY-MM-DD; priority: 紧急/高/中/低，支持逗号分隔如"紧急,高"。"""
    result = query_tickets(ticket_type=ticket_type, status=status, date_range=date_range, priority=priority)
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def analyze_tickets_tool(analysis_type: str) -> str:
    """对工单数据进行统计分析。analysis_type必填：type_distribution/status_distribution/priority_distribution/trend/summary。"""
    result = analyze_tickets(analysis_type=analysis_type)
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def update_ticket_status_tool(ticket_id: str, new_status: str) -> str:
    """更新工单状态。ticket_id: 工单编号，必填; new_status: 待处理/处理中/已解决/已关闭。"""
    result = update_ticket_status(ticket_id=ticket_id, new_status=new_status)
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def assign_ticket_tool(ticket_id: str, assignee: str) -> str:
    """分配工单给处理人。ticket_id: 工单编号，必填; assignee: 处理人姓名，必填。"""
    result = assign_ticket(ticket_id=ticket_id, assignee=assignee)
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def add_ticket_reply_tool(ticket_id: str, content: str) -> str:
    """为工单添加回复。ticket_id: 工单编号，必填; content: 回复内容，必填。"""
    result = add_ticket_reply(ticket_id=ticket_id, content=content)
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def get_ticket_detail_tool(ticket_id: str) -> str:
    """获取工单详情（包含所有回复记录）。ticket_id: 工单编号，必填。"""
    result = get_ticket_detail(ticket_id=ticket_id)
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def search_solutions_tool(query: str) -> str:
    """搜索历史已解决工单中类似问题的解决方案。query: 问题描述文本，必填。"""
    result = search_solutions(query=query)
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def recommend_tickets_tool() -> str:
    """智能推荐分析：返回紧急未分配工单（含建议处理人）、积压预警、处理人工作量、关联工单群组、操作建议。无需参数。"""
    result = recommend_tickets()
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def web_search_tool(query: str) -> str:
    """联网搜索获取实时信息。query: 搜索关键词，必填。"""
    result = web_search(query=query)
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def get_schema_tool(table_name: str | None = None) -> str:
    """获取数据库表结构。table_name: 表名，可选，为None返回所有表概览。"""
    result = get_schema(table_name=table_name)
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def execute_sql_tool(sql: str) -> str:
    """执行只读SQL查询（仅允许SELECT/PRAGMA/EXPLAIN/WITH）。sql: SQL语句，必填。"""
    result = execute_sql(sql=sql)
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def execute_python_tool(code: str) -> str:
    """【仅限画图】用 Plotly(推荐)或 matplotlib 生成图表。go/px/plt/np 已预导入。最后一行返回 Figure 即可。严禁硬编码数据。"""
    result = execute_python(code=code)
    return json.dumps(result, ensure_ascii=False, indent=2)


ALL_TOOLS = [
    query_tickets_tool, analyze_tickets_tool, update_ticket_status_tool,
    assign_ticket_tool, add_ticket_reply_tool, get_ticket_detail_tool,
    search_solutions_tool, recommend_tickets_tool, web_search_tool,
    get_schema_tool, execute_sql_tool, execute_python_tool,
]

TOOL_MAP = {t.name: t for t in ALL_TOOLS}


# ============================================================
# 工具执行器（不变）
# ============================================================

TOOL_TIMEOUT = 10
TOOL_TIMEOUT_MAP = {"web_search_tool": 30, "execute_python_tool": 20}
CIRCUIT_BREAKER_THRESHOLD = 3
RETRY_BACKOFFS = [0.2, 0.4, 0.8]


def _create_llm(temperature: float | None = None) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        streaming=True,
        extra_body={"thinking": {"type": "disabled"}},
    )


def _execute_single_tool(tool_name: str, tool_args: dict, circuit_state: dict[str, int]) -> tuple[str, dict]:
    """执行单个工具，含超时/重试/熔断。返回 (结果字符串, 元信息)。"""
    meta = {"elapsed": 0.0, "retries": 0, "degraded": False, "tool_name": tool_name}

    failures = circuit_state.get(tool_name, 0)
    if failures >= CIRCUIT_BREAKER_THRESHOLD:
        logger.warning(f"[exec] {tool_name} 已熔断 ({failures} 次失败)")
        meta["degraded"] = True
        return json.dumps({"error": f"工具 {tool_name} 暂时不可用（已熔断）", "degraded": True}, ensure_ascii=False), meta

    tool_func = TOOL_MAP.get(tool_name)
    if tool_func is None:
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False), meta

    timeout = TOOL_TIMEOUT_MAP.get(tool_name, TOOL_TIMEOUT)
    last_error = None
    for attempt in range(len(RETRY_BACKOFFS) + 1):
        try:
            start = time.time()
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(tool_func.invoke, tool_args)
                result = future.result(timeout=timeout)
            meta["elapsed"] = round(time.time() - start, 3)
            meta["retries"] = attempt
            circuit_state[tool_name] = 0
            return str(result), meta
        except ThreadTimeoutError:
            last_error = f"超时（{timeout}s）"
        except Exception as e:
            last_error = str(e)
        if attempt < len(RETRY_BACKOFFS):
            time.sleep(RETRY_BACKOFFS[attempt])

    circuit_state[tool_name] = circuit_state.get(tool_name, 0) + 1
    meta["degraded"] = True
    meta["retries"] = len(RETRY_BACKOFFS)
    return json.dumps({"error": "工具执行失败", "detail": str(last_error)[:200], "degraded": True}, ensure_ascii=False), meta


def extract_final_output(messages: list) -> str:
    """从消息列表中提取最终 AI 回复。"""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content or ""
            if content.strip() and "<function_calls>" not in content:
                return content.strip()
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content or ""
            if content.strip():
                return content.strip()
    return "无法生成回复，请重试。"


def _build_initial_messages(chat_history: list[dict[str, str]] | None) -> list:
    """将对话历史转为 LangChain 消息列表。"""
    msgs = []
    if chat_history:
        for m in chat_history[-6:]:
            role = m.get("role", "")
            content = m.get("content", "")
            if not content:
                continue
            if role == "user":
                msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                msgs.append(AIMessage(content=content))
    return msgs


# ============================================================
# v5.0 运行函数 — AgentLoop 驱动
# ============================================================

async def run_graph(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """v5.0: AgentLoop 自循环运行，返回最终结果。"""
    logger.info(f"[graph] 开始: '{user_input[:60]}...'")

    settings = get_settings()
    verbose = settings.LOG_LEVEL.upper() == "DEBUG"

    llm = _create_llm()
    agent = AgentLoop(llm=llm, tools=ALL_TOOLS, execute_tool=_execute_single_tool, verbose=verbose)

    start_time = time.time()
    circuit_state: dict[str, int] = {}
    output = ""
    steps: list[dict[str, Any]] = []

    async for event in agent.run(user_input, chat_history, circuit_state):
        if event["type"] == "done":
            output = event.get("output", "")
            steps = event.get("steps", [])
        elif event["type"] == "error":
            output = event.get("message", "处理出错，请重试")
            break

    elapsed = time.time() - start_time
    logger.info(f"[graph] 完成: steps={len(steps)}, elapsed={elapsed:.1f}s")

    return {
        "output": output,
        "intermediate_steps": steps,
        "route": "",
        "intent": "",
        "rewritten_query": user_input,
        "context_info": None,
    }


async def run_graph_stream(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
):
    """v5.0: AgentLoop 流式运行，转发事件给前端。"""
    logger.info(f"[graph:stream] 开始: '{user_input[:60]}...'")

    settings = get_settings()
    verbose = settings.LOG_LEVEL.upper() == "DEBUG"

    llm = _create_llm()
    agent = AgentLoop(llm=llm, tools=ALL_TOOLS, execute_tool=_execute_single_tool, verbose=verbose)

    start_time = time.time()
    circuit_state: dict[str, int] = {}
    steps: list[dict[str, Any]] = []
    output = ""
    current_node = "agent"

    async for event in agent.run(user_input, chat_history, circuit_state):
        etype = event["type"]

        if etype == "plan":
            yield {
                "type": "progress",
                "node": "agent",
                "label": "制定计划...",
                "steps": steps,
                "route": "",
                "intent": "",
            }

        elif etype == "token":
            yield {"type": "token", "content": event["content"], "node": current_node}

        elif etype == "tool_call":
            current_node = "tool_executor"
            yield {
                "type": "progress",
                "node": "tool_executor",
                "label": f"执行工具: {event['tool_name']}",
                "steps": steps,
                "route": "",
                "intent": "",
            }

        elif etype == "step":
            step_data = {
                "action": event.get("action", ""),
                "action_input": event.get("action_input", ""),
                "observation": event.get("observation", ""),
                "elapsed": event.get("elapsed", 0),
            }
            steps.append(step_data)
            current_node = "agent"
            yield {
                "type": "progress",
                "node": "agent",
                "label": "观察结果...",
                "steps": steps,
                "route": "",
                "intent": "",
            }

        elif etype == "done":
            output = event.get("output", "")
            if not steps:
                steps = event.get("steps", [])

    elapsed = time.time() - start_time
    logger.info(f"[graph:stream] 完成: steps={len(steps)}, elapsed={elapsed:.1f}s")

    yield {
        "type": "done",
        "output": output,
        "intermediate_steps": steps,
        "route": "",
        "intent": "",
        "rewritten_query": user_input,
        "elapsed": round(elapsed, 1),
    }
