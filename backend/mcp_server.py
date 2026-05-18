# -*- coding: utf-8 -*-
"""MCP工具服务器 — 基于 mcp SDK 的 JSON-RPC 2.0 stdio 服务器"""

import asyncio
import json
import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from backend import init_app
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
from backend.logger import get_logger

# 初始化应用
init_app()
logger = get_logger(__name__)

# 创建 MCP Server
server = Server("mcp-ticket-agent")

# ============================================================
# 工具定义
# ============================================================

TOOL_DEFINITIONS = [
    Tool(
        name="query_tickets",
        description="按条件筛选工单列表。ticket_type: 设备故障/质量异常/安全隐患/物料短缺/工艺问题/生产计划/环境监测; status: 待处理/处理中/已解决/已关闭; priority: 紧急/高/中/低(支持逗号分隔如"紧急,高"); date_range: today/week/month/YYYY-MM-DD,YYYY-MM-DD。返回含设备/产线/物料FK引用的完整工单。",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_type": {"type": "string", "description": "工单类型：设备故障/质量异常/安全隐患/物料短缺/工艺问题/生产计划/环境监测"},
                "status": {"type": "string", "description": "工单状态：待处理/处理中/已解决/已关闭"},
                "date_range": {"type": "string", "description": "日期范围：today/week/month/YYYY-MM-DD,YYYY-MM-DD"},
                "priority": {"type": "string", "description": "优先级：紧急/高/中/低，支持逗号分隔如"紧急,高""},
            },
        },
    ),
    Tool(
        name="analyze_tickets",
        description="对工单数据进行统计分析。analysis_type 必填，可选: type_distribution/status_distribution/priority_distribution/trend/summary。",
        inputSchema={
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "description": "分析类型：type_distribution/status_distribution/priority_distribution/trend/summary",
                },
            },
            "required": ["analysis_type"],
        },
    ),
    Tool(
        name="update_ticket_status",
        description="更新工单状态。ticket_id: 工单编号，必填; new_status: 新状态（待处理/处理中/已解决/已关闭），必填。",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "工单编号"},
                "new_status": {"type": "string", "description": "新状态：待处理/处理中/已解决/已关闭"},
            },
            "required": ["ticket_id", "new_status"],
        },
    ),
    Tool(
        name="assign_ticket",
        description="分配工单给处理人。ticket_id: 工单编号，必填; assignee: 处理人姓名，必填。",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "工单编号"},
                "assignee": {"type": "string", "description": "处理人姓名"},
            },
            "required": ["ticket_id", "assignee"],
        },
    ),
    Tool(
        name="add_ticket_reply",
        description="为工单添加回复记录。ticket_id: 工单编号，必填; content: 回复内容，必填。",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "工单编号"},
                "content": {"type": "string", "description": "回复内容"},
            },
            "required": ["ticket_id", "content"],
        },
    ),
    Tool(
        name="get_ticket_detail",
        description="获取工单详情（包含所有回复记录）。ticket_id: 工单编号，必填。",
        inputSchema={
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "工单编号"},
            },
            "required": ["ticket_id"],
        },
    ),
    Tool(
        name="search_solutions",
        description="搜索历史已解决工单中的类似问题方案。query: 问题描述文本，必填。",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "问题描述文本"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="recommend_tickets",
        description="智能推荐分析：返回紧急未分配工单（含建议处理人）、积压预警、处理人工作量分布、关联工单群组、操作建议。无需参数。",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="web_search",
        description="联网搜索获取实时信息。query: 搜索关键词，必填。",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_schema",
        description="获取数据库表结构。共12张表：tickets(工单)/equipment(设备)/production_lines(产线)/materials(物料)/quality_metrics(质量指标)/ticket_replies(回复)/conversations(对话)等。table_name可选，为None返回所有表概览。",
        inputSchema={
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "表名，可选。如tickets/equipment/materials等"},
            },
        },
    ),
    Tool(
        name="execute_sql",
        description="执行只读SQL查询（仅允许SELECT/PRAGMA/EXPLAIN/WITH）。sql: SQL语句，必填。常用模板见sql_templates表。示例：SELECT * FROM tickets WHERE created_at = date('now')",
        inputSchema={
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "只读SQL查询语句（仅SELECT/PRAGMA）"},
            },
            "required": ["sql"],
        },
    ),
    Tool(
        name="execute_python",
        description="在受限沙箱中执行Python代码用于数据分析。可用模块：json/datetime/math/statistics/collections/itertools。code: Python代码，必填。最后一行若为表达式自动求值并返回。",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python代码"},
            },
            "required": ["code"],
        },
    ),
]

# 工具执行映射
TOOL_HANDLERS = {
    "query_tickets": query_tickets,
    "analyze_tickets": analyze_tickets,
    "update_ticket_status": update_ticket_status,
    "assign_ticket": assign_ticket,
    "add_ticket_reply": add_ticket_reply,
    "get_ticket_detail": get_ticket_detail,
    "search_solutions": search_solutions,
    "recommend_tickets": recommend_tickets,
    "web_search": web_search,
    "get_schema": get_schema,
    "execute_sql": execute_sql,
    "execute_python": execute_python,
}


# ============================================================
# MCP 处理器
# ============================================================

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """返回所有可用工具列表。"""
    logger.info("[MCP] list_tools 请求")
    return TOOL_DEFINITIONS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """处理工具调用请求。"""
    logger.info(f"[MCP] call_tool: {name}, 参数: {arguments}")

    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return [TextContent(type="text", text=json.dumps(
            {"error": f"未知工具: {name}"}, ensure_ascii=False
        ))]

    try:
        result = handler(**arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except Exception as e:
        logger.error(f"[MCP] 工具 {name} 执行失败: {str(e)}")
        return [TextContent(type="text", text=json.dumps(
            {"error": f"工具执行失败: {str(e)}"}, ensure_ascii=False
        ))]


# ============================================================
# 入口
# ============================================================

async def main():
    """启动 MCP stdio 服务器。"""
    logger.info("MCP 工具服务器正在启动 (stdio)...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
