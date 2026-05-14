# -*- coding: utf-8 -*-
"""定时任务调度 — 主动监控：告警检测 + 日报生成 + 轮询机制"""

import json
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from backend.database import get_connection
from backend.logger import get_logger

logger = get_logger(__name__)

# 全局告警缓存（线程安全）
_alert_cache: dict = {"alerts": [], "last_check": None, "_lock": threading.Lock()}


def check_urgent_alerts() -> list[dict[str, Any]]:
    """检测紧急告警条件，返回告警列表。

    告警规则：
    - 紧急工单 >= 3 个 → danger
    - 超 24 小时未分配的高优工单 → warning
    - 待处理工单积压 > 5 个 → warning
    """
    conn = get_connection()
    try:
        now = datetime.now()
        yesterday = (now - timedelta(hours=24)).strftime("%Y-%m-%d")
        alerts = []

        # 规则1：紧急 + 高优工单数量
        urgent_count = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE priority IN ('紧急','高') "
            "AND status IN ('待处理','处理中')"
        ).fetchone()[0]
        if urgent_count >= 3:
            urgent_rows = conn.execute(
                "SELECT ticket_id, title FROM tickets WHERE priority IN ('紧急','高') "
                "AND status IN ('待处理','处理中') ORDER BY created_at DESC LIMIT 5"
            ).fetchall()
            alerts.append({
                "level": "danger",
                "title": f"{urgent_count} 个紧急工单待处理",
                "detail": "；".join(f"{r['ticket_id']}: {r['title'][:25]}..." for r in urgent_rows),
                "count": urgent_count,
            })

        # 规则2：超 24h 未分配
        stale_unassigned = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE status IN ('待处理','处理中') "
            "AND (assignee IS NULL OR assignee = '') AND created_at <= ?",
            (yesterday,),
        ).fetchone()[0]
        if stale_unassigned > 0:
            stale_rows = conn.execute(
                "SELECT ticket_id, title, created_at FROM tickets "
                "WHERE status IN ('待处理','处理中') AND (assignee IS NULL OR assignee = '') "
                "AND created_at <= ? ORDER BY created_at LIMIT 5",
                (yesterday,),
            ).fetchall()
            alerts.append({
                "level": "warning",
                "title": f"{stale_unassigned} 个工单超 24h 未分配",
                "detail": "；".join(
                    f"{r['ticket_id']}({r['created_at']})" for r in stale_rows
                ),
                "count": stale_unassigned,
            })

        # 规则3：待处理积压
        pending_count = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE status = '待处理'"
        ).fetchone()[0]
        if pending_count > 5:
            alerts.append({
                "level": "warning",
                "title": f"待处理工单积压 {pending_count} 个",
                "detail": "建议优先分配和跟进",
                "count": pending_count,
            })

        # 写入缓存
        with _alert_cache["_lock"]:
            _alert_cache["alerts"] = alerts
            _alert_cache["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")

        return alerts
    finally:
        conn.close()


def get_cached_alerts() -> dict:
    """获取最近一次告警检测结果。"""
    with _alert_cache["_lock"]:
        return {
            "alerts": _alert_cache["alerts"],
            "last_check": _alert_cache["last_check"],
        }


def generate_report_text(stats: dict) -> str:
    """生成日报结构化文本（不依赖 LLM 的快速版本）。

    日报结构：概览 → 紧急事项 → 处理人负荷 → 趋势 → 建议
    """
    conn = get_connection()
    try:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        # 今日工单
        today_tickets = [
            dict(r) for r in conn.execute(
                "SELECT * FROM tickets WHERE created_at = ?", (today,)
            ).fetchall()
        ]

        # 紧急工单
        urgent = [
            dict(r) for r in conn.execute(
                "SELECT * FROM tickets WHERE priority IN ('紧急','高') "
                "AND status IN ('待处理','处理中')"
            ).fetchall()
        ]

        # 处理人负荷
        workload = {}
        rows = conn.execute(
            "SELECT assignee, COUNT(*) as cnt FROM tickets "
            "WHERE assignee != '' AND status IN ('待处理','处理中') "
            "GROUP BY assignee ORDER BY cnt DESC"
        ).fetchall()
        for r in rows:
            workload[r["assignee"]] = r["cnt"]

        # 状态分布
        status_counts = {}
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tickets GROUP BY status"
        ).fetchall()
        for r in rows:
            status_counts[r["status"]] = r["cnt"]

        # 积压
        week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        stale = [
            dict(r) for r in conn.execute(
                "SELECT * FROM tickets WHERE status = '待处理' AND created_at <= ?",
                (week_ago,),
            ).fetchall()
        ]

        # 构建报告
        lines = [
            f"# 工单日报 — {now.strftime('%Y年%m月%d日')}",
            "",
            "## 概览",
            f"- 工单总数: {stats.get('total', 0)}",
            f"- 待处理: {stats.get('pending', 0)}",
            f"- 处理中: {stats.get('processing', 0)}",
            f"- 今日新增: {stats.get('today', 0)}",
            "",
            "## 状态分布",
        ]
        for st_name, cnt in status_counts.items():
            lines.append(f"- {st_name}: {cnt}")

        lines.append("")
        lines.append("## 紧急事项")
        if urgent:
            for t in urgent:
                lines.append(f"- **{t['ticket_id']}** [{t['priority']}] {t['title'][:50]}")
        else:
            lines.append("- 无紧急事项，状态正常。")

        lines.append("")
        lines.append("## 处理人负荷")
        if workload:
            for name, cnt in workload.items():
                bar = "█" * cnt
                lines.append(f"- {name}: {bar} {cnt}")
        else:
            lines.append("- 暂无分配记录。")

        lines.append("")
        lines.append("## 积压预警")
        if stale:
            for t in stale:
                days_ago = (now - datetime.strptime(t["created_at"], "%Y-%m-%d")).days
                lines.append(f"- **{t['ticket_id']}** 已积压 {days_ago} 天: {t['title'][:40]}")
        else:
            lines.append("- 无长期积压工单。")

        lines.append("")
        lines.append("## 建议")
        if urgent:
            lines.append(f"- 优先处理 {len(urgent)} 个紧急/高优工单")
        pending = stats.get("pending", 0)
        if pending > 3:
            lines.append(f"- {pending} 个待处理工单建议分配处理人")
        if not urgent and pending <= 3:
            lines.append("- 工单状态良好，保持日常跟进即可。")

        return "\n".join(lines)
    finally:
        conn.close()
