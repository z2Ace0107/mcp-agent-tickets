# -*- coding: utf-8 -*-
"""MCP工具服务器 — FastAPI 暴露工单查询与分析工具"""

import sys
import os

# 确保项目根目录在 sys.path 中，支持独立启动
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.tools import query_tickets, analyze_tickets

app = FastAPI(title="MCP智能工单Agent系统 - 工具服务器", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Health
# ============================================================

@app.get("/health")
async def health():
    """健康检查。"""
    return {"status": "ok", "service": "mcp-ticket-tools"}


# ============================================================
# MCP 工具端点
# ============================================================

@app.get("/tools/query_tickets")
async def api_query_tickets(
    ticket_type: str | None = Query(None, description="工单类型：退款/技术/咨询/投诉"),
    status: str | None = Query(None, description="工单状态：待处理/处理中/已解决/已关闭"),
    date_range: str | None = Query(None, description="日期范围：today/week/month/YYYY-MM-DD,YYYY-MM-DD"),
):
    """按条件筛选工单列表。"""
    result = query_tickets(ticket_type=ticket_type, status=status, date_range=date_range)
    return {"success": True, "data": result, "count": len(result)}


@app.get("/tools/analyze_tickets")
async def api_analyze_tickets(
    analysis_type: str = Query(..., description="分析类型：type_distribution/status_distribution/priority_distribution/trend/summary"),
):
    """对工单数据进行统计分析。"""
    result = analyze_tickets(analysis_type=analysis_type)
    success = "error" not in result
    return {"success": success, "data": result}


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("MCP_SERVER_PORT", "8000"))
    uvicorn.run("backend.mcp_server:app", host="0.0.0.0", port=port, reload=True)
