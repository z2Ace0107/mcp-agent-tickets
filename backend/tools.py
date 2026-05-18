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
    priority: str | None = None,
) -> list[dict[str, Any]]:
    """按条件筛选工单列表。

    Args:
        ticket_type: 工单类型，可选值：设备故障/质量异常/安全隐患/物料短缺/工艺问题/生产计划/环境监测。为None则不筛选类型。
        status: 工单状态，可选值：待处理/处理中/已解决/已关闭。为None则不筛选状态。
        date_range: 日期范围，可选格式：
            - "today" — 当天
            - "week" — 近7天
            - "month" — 近30天
            - "YYYY-MM-DD,YYYY-MM-DD" — 自定义范围
            为None则不限日期。
        priority: 优先级筛选，可选值：紧急/高/中/低。支持多值逗号分隔，如"紧急,高"同时匹配紧急和高优先。为None则不筛选。

    Returns:
        匹配条件的工单列表，每条工单为包含完整字段的字典。
    """
    return query_tickets_db(
        ticket_type=ticket_type, status=status, date_range=date_range, priority=priority,
    )


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
    """使用百度AI搜索获取互联网实时信息。

    Args:
        query: 搜索关键词，必填。
        max_results: 最大返回结果数，默认 5。

    Returns:
        {"query": str, "results": [{"title": str, "url": str, "snippet": str}, ...]}
    """
    import httpx
    from backend.config import get_settings

    settings = get_settings()
    try:
        resp = httpx.post(
            f"{settings.BAIDU_SEARCH_BASE_URL}/web_search",
            headers={
                "Authorization": f"Bearer {settings.BAIDU_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "messages": [{"content": query, "role": "user"}],
                "search_source": "baidu_search_v2",
                "resource_type_filter": [{"type": "web", "top_k": max_results}],
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        references = data.get("references", [])
        return {
            "query": query,
            "results": [
                {"title": r["title"], "url": r.get("url", ""), "snippet": r.get("content", "")[:500]}
                for r in references[:max_results]
            ],
        }
    except Exception as e:
        return {"query": query, "results": [], "error": f"搜索失败: {str(e)}"}


# ============================================================
# v3.3 新增工具：Schema / SQL / Python
# ============================================================

def get_schema(table_name: str | None = None) -> dict[str, Any]:
    """获取数据库表结构信息。

    Args:
        table_name: 表名，可选。为 None 时返回所有表概览。

    Returns:
        {"tables": [...], "columns": [...]} 或单表详情
    """
    from backend.database import get_connection
    conn = get_connection()
    try:
        if table_name:
            rows = conn.execute(
                "SELECT * FROM db_schema_info WHERE table_name = ? ORDER BY is_primary_key DESC, id",
                (table_name,),
            ).fetchall()
            if not rows:
                # 回退：检查 sqlite_master
                table_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                ).fetchone()
                if not table_check:
                    return {"error": f"表不存在: {table_name}"}
                # 用 PRAGMA 获取列信息
                pragma_rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
                columns = [
                    {"column_name": r["name"], "data_type": r["type"],
                     "is_nullable": not r["notnull"], "is_primary_key": bool(r["pk"])}
                    for r in pragma_rows
                ]
                return {"table_name": table_name, "columns": columns, "source": "pragma"}
            return {
                "table_name": table_name,
                "columns": [
                    {"column_name": r["column_name"], "data_type": r["data_type"],
                     "is_nullable": bool(r["is_nullable"]), "is_primary_key": bool(r["is_primary_key"]),
                     "description": r["description"]}
                    for r in rows
                ],
                "source": "db_schema_info",
            }
        else:
            # 返回所有表概览
            table_rows = conn.execute(
                "SELECT DISTINCT table_name FROM db_schema_info ORDER BY table_name"
            ).fetchall()
            tables = []
            for tr in table_rows:
                tn = tr["table_name"]
                col_count = conn.execute(
                    "SELECT COUNT(*) FROM db_schema_info WHERE table_name = ?", (tn,)
                ).fetchone()[0]
                tables.append({"table_name": tn, "column_count": col_count})
            return {"tables": tables}
    finally:
        conn.close()


def execute_sql(sql: str) -> dict[str, Any]:
    """执行只读 SQL 查询（仅允许 SELECT/PRAGMA）。

    Args:
        sql: SQL 查询语句，必填。仅允许 SELECT 和 PRAGMA 语句。

    Returns:
        {"columns": [...], "rows": [...], "row_count": int}
    """
    import re
    from backend.database import get_connection

    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        return {"error": "SQL 语句为空"}

    # 安全检查：仅允许 SELECT 和 PRAGMA
    first_word = re.split(r'\s+', cleaned.upper())[0]
    allowed = {"SELECT", "PRAGMA", "EXPLAIN", "WITH"}
    if first_word not in allowed:
        return {
            "error": f"仅允许只读查询（SELECT/PRAGMA/EXPLAIN/WITH），不支持: {first_word}",
            "allowed_operations": list(allowed),
        }

    conn = get_connection()
    try:
        cursor = conn.execute(cleaned)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = [dict(r) for r in cursor.fetchall()]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }
    except Exception as e:
        return {"error": f"SQL 执行失败: {str(e)}", "sql": cleaned[:200]}
    finally:
        conn.close()


def execute_python(code: str) -> dict[str, Any]:
    """【仅限画图】用 plotly (推荐) 或 matplotlib 生成图表。严禁做数据分析。

    ⚠️ 必须先调其他工具拿到真实数据，再用本工具画图。严禁硬编码假数据。
    ⚠️ 推荐 Plotly：中文原生支持，交互式，无需字体配置。

    预导入: plotly.graph_objects(go), plotly.express(px), matplotlib.pyplot(plt), numpy(np)
    Plotly Figure 自动序列化为 JSON 供前端渲染。
    print() 输出被捕获。

    Args:
        code: Python 代码，最后一行返回 plotly Figure 即可。
    Returns:
        {"stdout": str, "error": str|None, "plotly_charts": [dict], "chart_images": [str(png base64)]}"""

    import sys
    import io
    import json as _json
    import math
    import statistics
    import collections
    import itertools
    import base64
    from datetime import datetime, timedelta
    import ast

    safe_locals = {
        "json": _json, "math": math, "statistics": statistics,
        "collections": collections, "itertools": itertools,
        "datetime": datetime, "timedelta": timedelta,
        "data": None,
    }

    # ── Plotly ──────────────────────────────────────────────────
    try:
        import plotly.graph_objects as _go
        import plotly.express as _px
        safe_locals["go"] = _go
        safe_locals["px"] = _px
    except ImportError:
        _go = None
        _px = None

    # ── Matplotlib ──────────────────────────────────────────────
    plt = None
    _sandbox_tmpdir = None
    try:
        import matplotlib
        matplotlib.use('Agg')
        matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        matplotlib.rcParams['axes.unicode_minus'] = False
        import matplotlib.font_manager as _fm
        _fm._load_fontmanager(try_read_cache=False)
        import matplotlib.pyplot as _plt
        import numpy as np

        import tempfile as _tempfile
        import os as _os
        _sandbox_tmpdir = _tempfile.mkdtemp(prefix="sandbox_")
        _original_savefig = _plt.savefig

        def _sandbox_savefig(filename, *args, **kwargs):
            if not _os.path.isabs(filename) and not _os.path.dirname(filename):
                filename = _os.path.join(_sandbox_tmpdir, _os.path.basename(filename))
            return _original_savefig(filename, *args, **kwargs)

        _plt.savefig = _sandbox_savefig

        safe_locals["plt"] = _plt
        safe_locals["np"] = np
        plt = _plt
    except ImportError:
        pass

    # 捕获 print 输出
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf

    if plt is not None:
        plt.close('all')

    try:
        tree = ast.parse(code.strip())
        if not tree.body:
            return {"stdout": "", "error": "空代码", "plotly_charts": [], "chart_images": []}

        *body_stmts, last_stmt = tree.body

        if body_stmts:
            prefix_code = "\n".join(ast.unparse(stmt) for stmt in body_stmts)
            exec(compile(prefix_code, "<sandbox>", "exec"), {"__builtins__": __builtins__}, safe_locals)

        if isinstance(last_stmt, ast.Expr):
            result = eval(
                compile(ast.Expression(body=last_stmt.value), "<sandbox>", "eval"),
                {"__builtins__": __builtins__},
                safe_locals,
            )
        else:
            stmt_code = ast.unparse(last_stmt)
            exec(compile(stmt_code, "<sandbox>", "exec"), {"__builtins__": __builtins__}, safe_locals)
            result = None

        # ── 收集 Plotly Figures ──────────────────────────────────
        plotly_charts = []
        if _go is not None:
            figures = []
            # 1) 返回值是 Figure
            if result is not None and isinstance(result, _go.Figure):
                figures.append(result)
            # 2) locals 中的 Figure（含 fig.show() 创建的）
            for name, val in safe_locals.items():
                if (isinstance(val, _go.Figure)
                        and val is not result
                        and name not in ("go", "px")):
                    figures.append(val)
            for fig in figures:
                try:
                    plotly_charts.append(_json.loads(fig.to_json()))
                except Exception:
                    pass

        # ── 收集 Matplotlib Figures ──────────────────────────────
        chart_images = []
        if plt is not None:
            for fig_num in plt.get_fignums():
                try:
                    fig = plt.figure(fig_num)
                    img_buf = io.BytesIO()
                    fig.savefig(img_buf, format='png', dpi=100, bbox_inches='tight')
                    img_buf.seek(0)
                    chart_images.append(base64.b64encode(img_buf.read()).decode('utf-8'))
                    plt.close(fig)
                except Exception:
                    pass

        # 序列化 result
        result_json = None
        if result is not None and not isinstance(result, _go.Figure if _go else object):
            try:
                result_json = _json.dumps(result, ensure_ascii=False)
            except (TypeError, ValueError):
                result_json = str(result)

        return {
            "stdout": buf.getvalue(),
            "result": result_json,
            "error": None,
            "plotly_charts": plotly_charts,
            "chart_images": chart_images,
        }
    except Exception as e:
        return {
            "stdout": buf.getvalue(),
            "result": None,
            "error": f"{type(e).__name__}: {str(e)}",
            "plotly_charts": [],
            "chart_images": [],
        }
    finally:
        sys.stdout = old_stdout
        if _sandbox_tmpdir is not None:
            import shutil as _shutil
            try:
                _shutil.rmtree(_sandbox_tmpdir, ignore_errors=True)
            except Exception:
                pass
