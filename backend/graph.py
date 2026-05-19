# -*- coding: utf-8 -*-
"""v3.3 LangGraph 4节点图 — classify → plan → execute → reflect (Self-Correction)"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as ThreadTimeoutError
from datetime import datetime
from typing import Any, Annotated, TypedDict

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage

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
# Prompts 由各 node 文件独立引用，graph.py 不再统一 import
from backend.config import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)


def strip_reasoning_content(messages: list) -> list:
    """移除消息中 DeepSeek thinking 产生的 reasoning_content。
    每个节点独立调用 API 时，不能携带前序节点的 reasoning_content，
    否则 DeepSeek 要求原样交还，导致 400 错误。
    """
    for m in messages:
        if hasattr(m, "additional_kwargs") and m.additional_kwargs:
            m.additional_kwargs.pop("reasoning_content", None)
    return messages


# ============================================================
# 12 个 LangChain 工具 — 全部注册到 function calling
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
    """执行只读SQL查询（仅允许SELECT/PRAGMA/EXPLAIN/WITH）。sql: SQL语句，必填。常用查询：SELECT * FROM tickets WHERE created_at = date('now')。"""
    result = execute_sql(sql=sql)
    return json.dumps(result, ensure_ascii=False, indent=2)

@tool
def execute_python_tool(code: str) -> str:
    """【仅限画图】用 Plotly(推荐)或 matplotlib 生成图表。Plotly 中文原生支持无乱码。go/px/plt/np 已预导入。最后一行返回 Figure 即可。严禁硬编码数据——数据必须来自其他工具的真实返回结果。"""
    result = execute_python(code=code)
    return json.dumps(result, ensure_ascii=False, indent=2)


ALL_TOOLS = [
    query_tickets_tool,
    analyze_tickets_tool,
    update_ticket_status_tool,
    assign_ticket_tool,
    add_ticket_reply_tool,
    get_ticket_detail_tool,
    search_solutions_tool,
    recommend_tickets_tool,
    web_search_tool,
    get_schema_tool,
    execute_sql_tool,
    execute_python_tool,
]

TOOL_MAP = {t.name: t for t in ALL_TOOLS}

# v3.3 工具子集 — 每个 Agent 只绑自己的工具
QUERY_TOOLS = [
    query_tickets_tool,
    get_ticket_detail_tool,
    execute_sql_tool,
    get_schema_tool,
    update_ticket_status_tool,
    assign_ticket_tool,
]

ANALYZE_TOOLS = [
    query_tickets_tool,  # v4.0 P1: 分析场景常需按日期/类型/优先级过滤
    analyze_tickets_tool,
    execute_python_tool,
    recommend_tickets_tool,
]

KNOWLEDGE_TOOLS = [
    search_solutions_tool,
    web_search_tool,
    get_ticket_detail_tool,
]

# v5.0: Reporter 节点已移除，Agent 最后回复直接作为最终输出

# ============================================================
# 状态定义
# ============================================================

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_input: str
    chat_history: list[dict[str, str]] | None
    intent: str
    rewritten_query: str
    route: str
    active_agent: str
    agent_iterations: int
    intermediate_steps: list[dict[str, Any]]
    circuit_state: dict[str, int]


# ============================================================
# 常量
# ============================================================

TOOL_TIMEOUT = 10
TOOL_TIMEOUT_MAP = {
    "web_search_tool": 30,  # 联网搜索允许更长超时
    "execute_python_tool": 20,  # Python 沙箱可能计算密集
}
CIRCUIT_BREAKER_THRESHOLD = 3
RETRY_BACKOFFS = [0.2, 0.4, 0.8]
MAX_AGENT_ITERATIONS = 5


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


# ============================================================
# 共享节点: 工具执行器（含自校正）
# ============================================================

def _execute_single_tool(tool_name: str, tool_args: dict, circuit_state: dict[str, int]) -> tuple[str, dict]:
    """执行单个工具，返回 (结果字符串, 元信息)。"""
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


def tool_executor_node(state: AgentState) -> dict:
    """执行工具调用，含超时/重试/熔断。"""
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_msg = messages[-1]
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return {}

    circuit_state = state.get("circuit_state", {})
    tool_messages = []
    steps = state.get("intermediate_steps", [])

    for tc in last_msg.tool_calls:
        tool_name = tc.get("name", "")
        tool_args = tc.get("args", {})
        tool_call_id = tc.get("id", "")

        observation, meta = _execute_single_tool(tool_name, tool_args, circuit_state)

        tool_messages.append(ToolMessage(content=observation, tool_call_id=tool_call_id))

        step_data = {
            "action": tool_name,
            "action_input": json.dumps(tool_args, ensure_ascii=False),
            "observation": observation[:2000],
            "elapsed": meta["elapsed"],
            "degraded": meta["degraded"],
            "retries": meta["retries"],
        }
        # 提取 execute_python 生成的图表数据，供前端渲染
        if tool_name == "execute_python_tool":
            try:
                obs_data = json.loads(observation)
                # matplotlib PNG 图表
                charts = obs_data.get("chart_images", [])
                if charts:
                    step_data["chart_images"] = charts
                # plotly JSON 图表
                plotly_charts = obs_data.get("plotly_charts", [])
                if plotly_charts:
                    step_data["plotly_charts"] = plotly_charts
            except (json.JSONDecodeError, KeyError):
                pass
        steps.append(step_data)

    return {
        "messages": tool_messages,
        "intermediate_steps": steps,
        "circuit_state": circuit_state,
        "agent_iterations": state.get("agent_iterations", 0) + 1,
    }


# ============================================================
# 路由函数
# ============================================================

def route_supervisor(state: AgentState) -> str:
    """After supervisor classification, route to target agent or END for chat."""
    route = state.get("route", "")
    if route in ("query_agent", "analyze_agent", "knowledge_agent"):
        return route
    return "END"  # chat → 直接结束，supervisor 已生成回复


def route_agent(state: AgentState) -> str:
    """After an agent node runs: more tools or END?"""
    if state.get("agent_iterations", 0) >= MAX_AGENT_ITERATIONS:
        return "END"
    messages = state.get("messages", [])
    if not messages:
        return "END"
    last_msg = messages[-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tool_executor"
    return "END"


def route_after_tools(state: AgentState) -> str:
    """After tool execution: back to agent or END."""
    if state.get("agent_iterations", 0) >= MAX_AGENT_ITERATIONS:
        return "END"
    return state.get("active_agent", "END")


# ============================================================
# 构建图
# ============================================================

def build_graph() -> StateGraph:
    """v5.0 4-Agent StateGraph: Supervisor → {Query|Analyze|Knowledge} → END。
    Reporter 节点已移除，Agent 最后回复直接作为最终输出。
    """
    from backend.nodes import supervisor_node, query_node, analyze_node, knowledge_node

    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("query_agent", query_node)
    workflow.add_node("analyze_agent", analyze_node)
    workflow.add_node("knowledge_agent", knowledge_node)
    workflow.add_node("tool_executor", tool_executor_node)

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor", route_supervisor,
        {"query_agent": "query_agent", "analyze_agent": "analyze_agent",
         "knowledge_agent": "knowledge_agent", "END": END},
    )

    for agent in ["query_agent", "analyze_agent", "knowledge_agent"]:
        workflow.add_conditional_edges(
            agent, route_agent,
            {"tool_executor": "tool_executor", "END": END},
        )

    workflow.add_conditional_edges(
        "tool_executor", route_after_tools,
        {"query_agent": "query_agent", "analyze_agent": "analyze_agent",
         "knowledge_agent": "knowledge_agent", "END": END},
    )

    return workflow.compile()


# ============================================================
# 便捷运行函数
# ============================================================

def extract_final_output(messages: list) -> str:
    """从消息列表中提取最终 AI 回复。跳过含 <function_calls> 的消息。"""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content or ""
            if content.strip() and "<function_calls>" not in content:
                return content.strip()
    # 回退：取任意非空消息
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content or ""
            if content.strip():
                return content.strip()
    return "无法生成回复，请重试。"


async def run_graph(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """运行 LangGraph 图，返回统一格式的结果。"""
    logger.info(f"[graph] 开始: '{user_input[:60]}...'")
    graph = build_graph()

    initial_state = {
        "messages": [],
        "user_input": user_input,
        "chat_history": chat_history,
        "intent": "",
        "rewritten_query": user_input,
        "route": "",
        "active_agent": "",
        "agent_iterations": 0,
        "intermediate_steps": [],
        "circuit_state": {},
    }

    start_time = time.time()
    final_state = graph.invoke(initial_state)
    elapsed = time.time() - start_time

    output = extract_final_output(final_state.get("messages", []))
    steps = final_state.get("intermediate_steps", [])
    intent = final_state.get("intent", "")
    route = final_state.get("route", "")
    rewritten = final_state.get("rewritten_query", user_input)

    logger.info(f"[graph] 完成: route={route}, steps={len(steps)}, elapsed={elapsed:.1f}s")

    return {
        "output": output,
        "intermediate_steps": steps,
        "route": route,
        "intent": intent,
        "rewritten_query": rewritten,
        "context_info": None,
    }


async def run_graph_stream(
    user_input: str,
    chat_history: list[dict[str, str]] | None = None,
):
    """v5.0: 流式运行 LangGraph 图。Agent 最后回复即最终输出，无 Reporter 节点。"""
    logger.info(f"[graph:stream] 开始: '{user_input[:60]}...'")
    graph = build_graph()

    initial_state = {
        "messages": [],
        "user_input": user_input,
        "chat_history": chat_history,
        "intent": "",
        "rewritten_query": user_input,
        "route": "",
        "active_agent": "",
        "agent_iterations": 0,
        "intermediate_steps": [],
        "circuit_state": {},
    }

    NODE_LABEL = {
        "supervisor": "分析意图...",
        "query_agent": "Query Agent 查询中...",
        "analyze_agent": "Analyze Agent 分析中...",
        "knowledge_agent": "Knowledge Agent 检索中...",
        "tool_executor": "执行工具...",
    }

    start_time = time.time()
    final_state = initial_state
    reported_nodes: set[str] = set()

    async for mode, data in graph.astream(initial_state, stream_mode=["updates", "messages"]):
        if mode == "updates":
            for node_name, update in data.items():
                node_reported = node_name in reported_nodes
                reported_nodes.add(node_name)

                for key, value in update.items():
                    if key == "messages":
                        existing = final_state.get("messages", [])
                        final_state["messages"] = existing + list(value) if value else existing
                    else:
                        final_state[key] = value

                if not node_reported:
                    label = NODE_LABEL.get(node_name, node_name)
                    steps = final_state.get("intermediate_steps", [])
                    route = final_state.get("route", "")
                    intent = final_state.get("intent", "")

                    yield {
                        "type": "progress",
                        "node": node_name,
                        "label": label,
                        "steps": steps,
                        "route": route,
                        "intent": intent,
                    }

        elif mode == "messages":
            message, metadata = data
            node_name = metadata.get("langgraph_node", "")
            if isinstance(message, AIMessageChunk):
                # 流式 thinking token（所有节点，thinking disabled 时无输出）
                reasoning = getattr(message, "additional_kwargs", {}) or {}
                reasoning_content = reasoning.get("reasoning_content")
                if reasoning_content:
                    yield {
                        "type": "thinking",
                        "content": reasoning_content,
                        "node": node_name,
                    }
                # 流式输出 token（Agent 节点的正文内容，不含工具调用）
                if (
                    message.content
                    and not getattr(message, "tool_calls", None)
                    and not getattr(message, "tool_call_chunks", None)
                ):
                    yield {"type": "token", "content": message.content, "node": node_name}

    output = extract_final_output(final_state.get("messages", []))
    steps = final_state.get("intermediate_steps", [])
    route = final_state.get("route", "")
    intent = final_state.get("intent", "")
    rewritten = final_state.get("rewritten_query", user_input)
    elapsed = time.time() - start_time

    logger.info(f"[graph:stream] 完成: route={route}, steps={len(steps)}, elapsed={elapsed:.1f}s")

    yield {
        "type": "done",
        "output": output,
        "intermediate_steps": steps,
        "route": route,
        "intent": intent,
        "rewritten_query": rewritten,
        "elapsed": round(elapsed, 1),
    }
