# -*- coding: utf-8 -*-
"""MCP工具定义 — 工单查询、分析、更新、分配、回复、详情"""

from typing import Any

from backend.database import (
    query_tickets_db,
    analyze_tickets_db,
    update_ticket_status_db,
    assign_ticket_db,
    add_ticket_reply_db,
    get_ticket_detail_db,
)


# ============================================================
# 查询与分析（兼容 v1.0 接口）
# ============================================================

def query_tickets(
    ticket_type: str | None = None,
    status: str | None = None,
    date_range: str | None = None,
) -> list[dict[str, Any]]:
    """按条件筛选工单列表。

    Args:
        ticket_type: 工单类型，可选值：退款/技术/咨询/投诉。为None则不筛选类型。
        status: 工单状态，可选值：待处理/处理中/已解决/已关闭。为None则不筛选状态。
        date_range: 日期范围，可选格式：
            - "today" — 当天
            - "week" — 近7天
            - "month" — 近30天
            - "YYYY-MM-DD,YYYY-MM-DD" — 自定义范围
            为None则不限日期。

    Returns:
        匹配条件的工单列表，每条工单为包含完整字段的字典。
    """
    return query_tickets_db(ticket_type=ticket_type, status=status, date_range=date_range)


def analyze_tickets(analysis_type: str) -> dict[str, Any]:
    """对工单数据进行统计分析。

    Args:
        analysis_type: 分析类型，可选值：
            - "type_distribution" — 按工单类型统计数量和占比
            - "status_distribution" — 按工单状态统计数量
            - "priority_distribution" — 按优先级统计数量
            - "trend" — 按日期统计每日新增工单趋势
            - "summary" — 全部维度的汇总统计

    Returns:
        统计结果字典，具体结构取决于 analysis_type。
    """
    return analyze_tickets_db(analysis_type=analysis_type)


# ============================================================
# 工单操作（v2.0 新增）
# ============================================================

def update_ticket_status(ticket_id: str, new_status: str) -> dict[str, Any]:
    """更新工单状态。

    Args:
        ticket_id: 工单编号，必填。
        new_status: 新状态，可选值：待处理/处理中/已解决/已关闭。

    Returns:
        更新后的工单字典，或包含 error 字段的错误信息。
    """
    return update_ticket_status_db(ticket_id=ticket_id, new_status=new_status)


def assign_ticket(ticket_id: str, assignee: str) -> dict[str, Any]:
    """分配工单给处理人。

    Args:
        ticket_id: 工单编号，必填。
        assignee: 处理人姓名，必填。

    Returns:
        更新后的工单字典，或包含 error 字段的错误信息。
    """
    return assign_ticket_db(ticket_id=ticket_id, assignee=assignee)


def add_ticket_reply(ticket_id: str, content: str) -> dict[str, Any]:
    """为工单添加回复记录。

    Args:
        ticket_id: 工单编号，必填。
        content: 回复内容，必填。

    Returns:
        回复记录字典，或包含 error 字段的错误信息。
    """
    return add_ticket_reply_db(ticket_id=ticket_id, content=content)


def get_ticket_detail(ticket_id: str) -> dict[str, Any]:
    """获取工单详情（含所有回复记录）。

    Args:
        ticket_id: 工单编号，必填。

    Returns:
        工单完整信息字典（含 replies 列表），或包含 error 字段的错误信息。
    """
    return get_ticket_detail_db(ticket_id=ticket_id)


# ============================================================
# RAG 检索（v2.0 新增）
# ============================================================

def search_solutions(query: str) -> dict[str, Any]:
    """搜索历史已解决工单中类似问题的解决方案。

    Args:
        query: 用户描述的问题文本，必填。

    Returns:
        {"query": str, "results": [{"similarity": float, "ticket_id": str, "title": str, ...}]}
    """
    from backend.rag import search_solutions as _search
    return _search(query)


def recommend_tickets() -> dict[str, Any]:
    """智能推荐分析：紧急工单识别、处理人建议、关联工单发现。

    Returns:
        {
            "urgent_unassigned": {...},    # 高优先分配工单 + 建议处理人
            "stale_warnings": {...},       # 积压超过7天的工单
            "workload_distribution": {...}, # 处理人工作量分布
            "related_groups": [...],        # 同类型活跃工单群组
            "recommended_actions": [...]   # 自然语言操作建议
        }
    """
    from backend.database import recommend_tickets_db
    return recommend_tickets_db()


def web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """使用 DuckDuckGo 搜索互联网获取实时信息。

    Args:
        query: 搜索关键词，必填。
        max_results: 最大返回结果数，默认 5。

    Returns:
        {"query": str, "results": [{"title": str, "url": str, "snippet": str}, ...]}
    """
    from ddgs import DDGS
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return {
            "query": query,
            "results": [
                {"title": r["title"], "url": r["href"], "snippet": r["body"]}
                for r in results
            ],
        }
    except Exception as e:
        return {"query": query, "results": [], "error": f"搜索失败: {str(e)}"}
