# -*- coding: utf-8 -*-
"""Streamlit 前端 — v2.0 深色主题"""

import asyncio
import json
import os
import sys
import threading
import time
from queue import Queue as SyncQueue
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from backend import init_app
from backend.agent import run_agent_stream
from backend.config import get_settings
from backend.scheduler import check_urgent_alerts, get_cached_alerts, generate_report_text

# ============================================================
# 常量
# ============================================================

ROUTE_LABELS = {
    "chat":          ("💬", "直接回复", "#93C5FD"),
    "simple_query":  ("⚡", "快速查询", "#4ADE80"),
    "complex":       ("🧠", "深度推理", "#C084FC"),
}
INTENT_LABELS = {
    "query": "查询工单", "analyze": "统计分析", "recommend": "智能推荐",
    "search": "搜索方案", "chat": "闲聊", "unknown": "未知",
}

TOOL_CN_MAP = {
    "query_tickets_tool":       "工单查询",
    "analyze_tickets_tool":     "工单分析",
    "update_ticket_status_tool":"更新状态",
    "assign_ticket_tool":       "分配处理人",
    "add_ticket_reply_tool":    "添加回复",
    "get_ticket_detail_tool":   "工单详情",
    "search_solutions_tool":    "检索方案",
    "recommend_tickets_tool":   "智能推荐",
    "web_search_tool":          "联网搜索",
    "get_schema_tool":          "查看Schema",
    "execute_sql_tool":         "执行SQL",
    "execute_python_tool":      "执行Python",
}

DEMO_SCENARIOS = {
    "— 演示场景 —": "",
    "今日工单概览":            "帮我查看今天所有工单的概况，并给出类型和状态分布",
    "智能推荐分析":            "帮我分析当前工单的优先级和紧急程度，给出处理建议和分配方案",
    "处理紧急设备故障":        "帮我找到所有待处理的紧急设备故障工单，分析影响的产线和建议处理方案",
    "质量异常追溯":            "查看最近一周的质量异常工单，分析根因和改进措施",
    "检索历史解决方案":        "曲轴淬火后变形率超标怎么办？有没有类似案例可以参考？",
    "生成工单处理报告":        "帮我生成一份今天的工单综合处理报告",
}

QUICK_ACTIONS = [
    ("📋 今日概览",   "帮我查看今天所有工单的概况，并给出类型和状态分布"),
    ("💡 智能推荐",   "帮我分析当前工单的优先级，给出处理建议和分配方案"),
    ("⚠️ 紧急工单",   "查看所有紧急和高优先级的未处理工单"),
    ("🔧 设备故障",   "查看最近一周的所有设备故障工单"),
    ("📊 统计报告",   "帮我生成一份今天的工单综合处理报告"),
]

# ============================================================
# CSS
# ============================================================

CUSTOM_CSS = """
<style>
/* =============================================================
   DeepSeek 极简风格 — v2.1
   设计语言：轻盈、透气、聚焦内容
   ============================================================= */

/* === 全局背景 === */
.stApp { background: #1b1c21 !important; font-size: 0.875rem; }
.main .block-container {
    padding: 1.5rem 2.5rem 1rem 2.5rem;
    max-width: 820px !important;
}
header[data-testid="stHeader"] { background: transparent !important; }

/* === 顶部标题 === */
.app-title {
    font-size: 1.05rem; font-weight: 500; letter-spacing: -0.01em;
    color: #ECECEC; display: flex; align-items: center; gap: 7px;
}
.app-title .badge {
    font-size: 0.65rem; font-weight: 400; color: #8B8B8B;
    background: rgba(255,255,255,0.06); padding: 1px 7px; border-radius: 8px;
}
.app-subtitle {
    font-size: 0.72rem; color: #8B8B8B; margin-top: 1px; font-weight: 400;
}

/* === 连接状态 === */
.status-tag {
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 0.75rem; padding: 2px 9px; border-radius: 10px; font-weight: 400;
}
.status-tag.online  { color: #4ADE80; background: rgba(74,222,128,0.08); }
.status-tag.offline { color: #8B8B8B; background: rgba(255,255,255,0.04); }
.status-dot { width: 5px; height: 5px; border-radius: 50%; display: inline-block; }
.status-dot.online  { background: #4ADE80; }
.status-dot.offline { background: #6B7280; }

/* === 统计卡片 — 幽灵卡片风格 === */
.stat-card {
    border-radius: 8px; padding: 0.75rem 0.9rem 0.7rem 0.9rem;
    border: 1px solid rgba(255,255,255,0.05);
    background: rgba(255,255,255,0.015);
    transition: border-color 0.15s;
}
.stat-card:hover { border-color: rgba(255,255,255,0.10); }
.stat-value {
    font-size: 1.45rem; font-weight: 600; line-height: 1.15;
    letter-spacing: -0.01em;
}
.stat-card.blue  .stat-value { color: #4D6BFE; }
.stat-card.amber .stat-value { color: #F59E0B; }
.stat-card.green .stat-value { color: #4ADE80; }
.stat-card.red   .stat-value { color: #EF4444; }
.stat-label {
    font-size: 0.7rem; color: #8B8B8B; margin-top: 2px; font-weight: 400;
}

/* === 全局按钮重置 === */
[data-testid="stButton"] button {
    border-radius: 6px !important; font-weight: 400 !important;
    transition: all 0.15s !important; font-size: 0.81rem !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    background: transparent !important; color: #D1D1D1 !important;
}
[data-testid="stButton"] button:hover {
    background: rgba(255,255,255,0.06) !important;
    border-color: rgba(255,255,255,0.14) !important; color: #ECECEC !important;
}
[data-testid="stButton"] button:active {
    background: rgba(255,255,255,0.10) !important; transform: scale(0.98) !important;
}

/* === 聊天气泡 === */
[data-testid="stChatMessage"] {
    border-radius: 10px !important; margin-bottom: 6px !important;
    padding: 0.15rem 0 !important; background: transparent !important;
}
[data-testid="stChatMessage"] p { line-height: 1.65; font-size: 0.875rem; }

/* === 聊天输入框 === */
[data-testid="stChatInput"] {
    padding: 0.5rem 0 1rem 0 !important;
}
[data-testid="stChatInput"] textarea {
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    background: rgba(255,255,255,0.03) !important;
    font-size: 0.875rem !important; min-height: 60px !important; transition: border-color 0.15s, box-shadow 0.15s;
    color: #ECECEC !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: #6B7280 !important; }
[data-testid="stChatInput"] textarea:focus {
    border-color: rgba(77,107,254,0.35) !important;
    box-shadow: 0 0 0 3px rgba(77,107,254,0.15) !important;
}

/* === 侧边栏 === */
section[data-testid="stSidebar"] {
    background: #1b1c21 !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
section[data-testid="stSidebar"] .block-container {
    padding: 1rem 0.75rem 0 0.75rem;
}
.section-label {
    font-size: 0.65rem; font-weight: 500; color: #6B7280;
    text-transform: uppercase; letter-spacing: 0.05em;
    margin: 0.85rem 0 0.3rem;
}

/* === 对话历史条目 === */
/* 标题按钮 — 单行截断 */
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="stButton"] button {
    max-width: 100%; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap; font-size: 0.76rem !important;
    justify-content: flex-start !important; padding: 4px 8px !important;
    border: none !important; background: transparent !important;
    border-radius: 5px !important;
}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="stButton"] button:hover {
    background: rgba(255,255,255,0.05) !important;
}
/* ⋯ 菜单按钮 — 低可见度，hover 才明显 */
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:last-child [data-testid="stButton"] button {
    opacity: 0.30 !important; transition: opacity 0.15s !important;
    font-size: 0.85rem !important; padding: 2px 4px !important;
    min-width: unset !important; border: none !important;
    background: transparent !important; color: #8B8B8B !important;
}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] [data-testid="stColumn"]:last-child [data-testid="stButton"] button:hover {
    opacity: 1.0 !important; color: #ECECEC !important;
    background: rgba(255,255,255,0.08) !important;
}

/* 侧边栏 caption（时间分组标题）*/
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    font-size: 0.7rem; color: #6B7280; font-weight: 400;
}

/* 提醒 — 内联轻量徽标 */
.alert-badge {
    display: flex; align-items: center; gap: 5px;
    font-size: 0.73rem; padding: 4px 7px; border-radius: 5px;
    margin-bottom: 2px; font-weight: 400;
}
.alert-badge.danger  { color: #FCA5A5; background: rgba(239,68,68,0.08); }
.alert-badge.warning { color: #FCD34D; background: rgba(245,158,11,0.08); }
.alert-badge.info   { color: #93C5FD; background: rgba(59,130,246,0.08); }
.alert-badge .dot {
    width: 4px; height: 4px; border-radius: 50%; flex-shrink: 0;
}
.alert-badge.danger .dot  { background: #EF4444; }
.alert-badge.warning .dot { background: #F59E0B; }
.alert-badge.info .dot   { background: #4D6BFE; }

/* === 弹出面板 === */
[data-testid="stPopover"] {
    min-width: 200px !important;
    border-radius: 8px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
}

/* === 输入框 === */
input[type="text"], input[type="password"], textarea {
    border-radius: 6px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    background: rgba(255,255,255,0.03) !important;
    color: #ECECEC !important; font-size: 0.81rem !important;
}

/* === 分割线 === */
hr { border-color: rgba(255,255,255,0.06) !important; margin: 0.5rem 0 !important; }

/* === 展开器（ReAct 推理过程）=== */
[data-testid="stExpander"] details {
    border: 1px solid rgba(255,255,255,0.06); border-radius: 8px;
}
[data-testid="stExpander"] summary {
    color: #8B8B8B; font-size: 0.8rem; font-weight: 400;
}

/* === 通知 === */
[data-testid="stNotification"] {
    border-radius: 8px !important;
}

/* === 无数据占位 === */
.empty-hint { color: #6B7280; font-size: 0.75rem; padding: 0.2rem 0; font-weight: 400; }

/* === v3.1 表格极简 === */
.markdown-table {
    width: 100%; border-collapse: collapse; font-size: 0.82rem;
}
.markdown-table thead th {
    text-align: left; font-weight: 400; color: #6B7280;
    font-size: 0.72rem; padding: 6px 10px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
.markdown-table tbody td {
    padding: 5px 10px; color: #D1D1D1;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.markdown-table tbody tr:hover { background: rgba(255,255,255,0.02); }

/* === Scrollbar === */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.14); }
</style>

<script>
// 推理面板增强：展开滚动修正 + 底部收起按钮
(function() {
    function setupExpander(details) {
        if (details.dataset.enhanced) return;
        details.dataset.enhanced = '1';

        var summary = details.querySelector('summary');
        if (!summary) return;

        // 1. 展开时滚到面板顶部
        summary.addEventListener('click', function() {
            setTimeout(function() {
                if (details.hasAttribute('open')) {
                    summary.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 80);
        });

        // 2. 底部注入收起按钮
        var btn = document.createElement('button');
        btn.textContent = '收起 ▲';
        btn.style.cssText = 'display:block;margin:8px auto 0;font-size:0.7rem;' +
            'color:#8B8B8B;background:rgba(255,255,255,0.03);' +
            'border:1px solid rgba(255,255,255,0.08);border-radius:4px;' +
            'cursor:pointer;padding:2px 14px;';
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            details.open = false;
        });
        details.appendChild(btn);
    }

    function scanExpanders() {
        var detailsList = window.parent.document.querySelectorAll(
            '[data-testid="stExpander"] details'
        );
        detailsList.forEach(setupExpander);
    }

    scanExpanders();
    new MutationObserver(scanExpanders).observe(
        window.parent.document.body, { childList: true, subtree: true }
    );
})();
</script>
"""

# ============================================================
# 页面配置
# ============================================================

st.set_page_config(
    page_title="LineMind",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 初始化
# ============================================================

if "app_initialized" not in st.session_state:
    with st.spinner("正在初始化系统..."):
        init_app()
    st.session_state.app_initialized = True

settings = get_settings()
api_key = os.environ.get("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY
HAS_API_KEY = bool(api_key)
if HAS_API_KEY:
    os.environ["DEEPSEEK_API_KEY"] = api_key

# ============================================================
# 会话状态
# ============================================================

st.session_state.setdefault("chat_history", [])
st.session_state.setdefault("pending_prompt", None)
st.session_state.setdefault("note_target", None)
st.session_state.setdefault("export_target", None)
st.session_state.setdefault("api_key_set", HAS_API_KEY)
st.session_state.setdefault("show_timestamps", True)
st.session_state.setdefault("auto_expand_react", False)
st.session_state.setdefault("current_conversation_id", None)
st.session_state.setdefault("_saved_msg_count", 0)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ============================================================
# 工具函数
# ============================================================

def fetch_ticket_stats():
    from backend.database import get_connection
    conn = get_connection()
    try:
        total   = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM tickets WHERE status='待处理'").fetchone()[0]
        process = conn.execute("SELECT COUNT(*) FROM tickets WHERE status='处理中'").fetchone()[0]
        urgent  = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE priority IN ('紧急','高') AND status IN ('待处理','处理中')"
        ).fetchone()[0]
        today_count = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE created_at = ?",
            (datetime.now().strftime("%Y-%m-%d"),)
        ).fetchone()[0]
        # 最紧急工单标题用于提醒
        top_urgent = conn.execute(
            "SELECT ticket_id, title FROM tickets WHERE priority IN ('紧急','高') "
            "AND status IN ('待处理','处理中') ORDER BY "
            "CASE priority WHEN '紧急' THEN 0 ELSE 1 END, created_at DESC LIMIT 1"
        ).fetchone()
        return {"total": total, "pending": pending, "processing": process,
                "urgent": urgent, "today": today_count,
                "top_urgent_id": top_urgent["ticket_id"] if top_urgent else None,
                "top_urgent_title": top_urgent["title"] if top_urgent else None}
    finally:
        conn.close()


def convert_markdown_table(text: str) -> str:
    """将 Markdown 表格转换为卡片式列表格式，提升可读性。"""
    import re

    def _is_separator(line: str) -> bool:
        parts = [c.strip() for c in line.strip("|").split("|")]
        return all(re.match(r"^[\s\-:]+$", p) for p in parts if p)

    lines = text.split("\n")
    result = []
    in_table = False
    table_lines = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\|.+\|$", stripped):
            if _is_separator(stripped):
                continue
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(stripped)
        else:
            if in_table and table_lines:
                result.append(_table_to_kv(table_lines))
                table_lines = []
                in_table = False
            result.append(line)

    if in_table and table_lines:
        result.append(_table_to_kv(table_lines))

    return "\n".join(result)


def _table_to_kv(lines: list[str]) -> str:
    """将表格行转换为卡片式多行格式。

    2 列 -> 单行: ● Key: Value
    3+ 列 -> 多行卡片: 首列加粗标题，其余字段缩进换行
    """
    cols = [c.strip() for c in lines[0].strip("|").split("|")]
    out = []
    for line in lines[1:]:
        vals = [c.strip() for c in line.strip("|").split("|")]
        if len(vals) != len(cols):
            continue
        if len(cols) == 2:
            out.append(f"● **{vals[0]}**: {vals[1]}")
        else:
            # 多列 → 卡片式：首列加粗作标题，其余字段缩进换行
            title = vals[0]
            fields = "\n".join(f"  {cols[i]}: {vals[i]}" for i in range(1, len(cols)))
            out.append(f"● **{title}**\n{fields}")
    return "\n".join(out)


def render_reAct_steps(msg: dict):
    """渲染推理步骤面板 — v3.0: 含步骤 0 预处理 + 工具耗时/裁剪标记。"""
    steps = msg.get("steps", [])
    route = msg.get("route", "")
    intent = msg.get("intent", "")
    rewritten = msg.get("rewritten_query", "")

    # 无步骤且无路由信息时直接返回
    if not steps and not route:
        return

    # 面板标题
    step_count = len(steps)
    if route == "chat":
        title_parts = ["推理过程（💬 直接回复）"]
    elif step_count == 0:
        title_parts = ["推理过程（0 步）"]
    else:
        title_parts = [f"推理过程（{step_count} 步）"]

    expanded = st.session_state.get("auto_expand_react", False)
    with st.expander("  ".join(title_parts), expanded=expanded):
        # ---- 步骤 0: 预处理结果 ----
        if route and route != "chat":
            route_icon, route_label, route_color = ROUTE_LABELS.get(route, ("", route, "#8B8B8B"))
            intent_cn = INTENT_LABELS.get(intent, intent)
            st.markdown(
                f'<span style="display:inline-flex;align-items:center;gap:6px;font-size:0.82rem;color:{route_color};">'
                f'{route_icon} <b>步骤 0</b> — 意图识别</span>',
                unsafe_allow_html=True,
            )
            st.caption(f"意图：{intent_cn}　|　路由：{route_icon} {route_label}")
            if rewritten:
                st.caption(f"改写：{rewritten[:120]}{'...' if len(rewritten) > 120 else ''}")
            if steps:
                st.divider()

        # ---- 工具步骤 ----
        for si, step in enumerate(steps, 1):
            tool_name = step.get("action", "unknown")
            tool_cn = TOOL_CN_MAP.get(tool_name, tool_name)
            elapsed = step.get("elapsed", 0)
            trimmed = step.get("trimmed", False)
            degraded = step.get("degraded", False)
            retries = step.get("retries", 0)
            orig_len = step.get("original_length", 0)

            # 步骤标题 + 状态徽标
            status_html = ""
            if degraded:
                status_html = (
                    ' <span style="font-size:0.65rem;color:#FCA5A5;'
                    'background:rgba(239,68,68,0.1);padding:0px 5px;border-radius:4px;">降级</span>'
                )
            elif trimmed:
                status_html = (
                    ' <span style="font-size:0.65rem;color:#FCD34D;'
                    'background:rgba(245,158,11,0.1);padding:0px 5px;border-radius:4px;">已裁剪</span>'
                )
            st.markdown(
                f"**步骤 {si}** — {tool_cn}{status_html}",
                unsafe_allow_html=True,
            )

            # 耗时 + 字符数
            meta_parts = []
            if elapsed > 0:
                meta_parts.append(f"⏱ {elapsed}s")
            if orig_len > 0:
                meta_parts.append(f"📄 {orig_len} 字符")
            if trimmed:
                meta_parts.append("✂ 已裁剪")
            if retries > 0:
                meta_parts.append(f"🔄 重试 {retries} 次")
            if meta_parts:
                st.caption("  ".join(meta_parts))

            # 思考过程
            thought = step.get("thought", "")
            if thought:
                st.markdown(f"*{thought[:300]}*")

            # 参数
            try:
                args_str = step.get("action_input", "{}")
                args_parsed = json.loads(args_str) if isinstance(args_str, str) else args_str
                st.code(json.dumps(args_parsed, ensure_ascii=False, indent=2), language="json")
            except Exception:
                st.text(str(step.get("action_input", ""))[:500])

            # 观察结果
            obs = str(step.get("observation", ""))
            if len(obs) > 600:
                st.caption(f"数据较长（{len(obs)} 字符），仅显示前 600 字符：")
                st.code(obs[:600], language="json")
            elif obs:
                st.code(obs, language="json")

            # 图表渲染（execute_python 生成）
            _render_python_charts(step)

            if si < len(steps):
                st.divider()


def _render_python_charts(step: dict) -> None:
    """渲染 execute_python 生成的图表（Plotly 优先，matplotlib 兜底）。"""
    import base64 as _b64
    import plotly.graph_objects as _go

    plotly_charts = step.get("plotly_charts", [])
    chart_images = step.get("chart_images", [])

    for chart_dict in plotly_charts:
        try:
            fig = _go.Figure(chart_dict)
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass

    # matplotlib PNG 兜底
    if chart_images:
        for img_b64 in chart_images:
            l, c, r = st.columns([1.5, 7, 1.5])
            with c:
                st.image(_b64.b64decode(img_b64), use_container_width=True)


def render_charts_from_steps(steps: list):
    """从步骤列表中提取图表数据并渲染。"""
    for step in steps:
        _render_python_charts(step)


def save_current_conversation():
    if not st.session_state.chat_history:
        return
    from backend.database import create_conversation, save_message, update_conversation_title
    conv_id = st.session_state.current_conversation_id
    saved_count = st.session_state.get("_saved_msg_count", 0)
    new_msgs = st.session_state.chat_history[saved_count:]
    if not new_msgs:
        return
    if conv_id is None:
        first_user = next(
            (m["content"] for m in st.session_state.chat_history if m["role"] == "user"),
            "新对话",
        )
        title = first_user[:50] + ("..." if len(first_user) > 50 else "")
        conv_id = create_conversation(title)
        st.session_state.current_conversation_id = conv_id
    for msg in new_msgs:
        steps_json = json.dumps(msg.get("steps", []), ensure_ascii=False)
        save_message(conv_id, msg["role"], msg["content"], steps_json)
    st.session_state._saved_msg_count = len(st.session_state.chat_history)
    # 用第一条用户消息更新标题
    first_user = next(
        (m["content"] for m in st.session_state.chat_history if m["role"] == "user"),
        "新对话",
    )
    title = first_user[:50] + ("..." if len(first_user) > 50 else "")
    update_conversation_title(conv_id, title)


def load_conversation_history(conv_id: int) -> bool:
    from backend.database import load_conversation
    conv = load_conversation(conv_id)
    if not conv:
        return False
    st.session_state.chat_history = conv["messages"]
    st.session_state.current_conversation_id = conv_id
    st.session_state._saved_msg_count = len(conv["messages"])
    return True


def start_new_conversation():
    st.session_state.chat_history = []
    st.session_state.current_conversation_id = None
    st.session_state._saved_msg_count = 0


def _generate_short_title(text: str) -> str | None:
    """调用 LLM 生成不超过 15 字的短标题。失败返回 None。"""
    try:
        from openai import OpenAI
        settings = get_settings()
        api_key = os.environ.get("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY
        if not api_key:
            return None
        client = OpenAI(api_key=api_key, base_url=settings.DEEPSEEK_BASE_URL)
        resp = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[{
                "role": "user",
                "content": f"将以下对话内容总结为不超过15个字的标题，只输出标题本身，不要加引号或任何额外文字：\n\n{text}",
            }],
            max_tokens=32,
            temperature=0,
            extra_body={"thinking": {"type": "disabled"}},
        )
        result = resp.choices[0].message.content.strip()
        result = result.replace('"', '').replace('《', '').replace('》', '').replace('「', '').replace('」', '')
        return result[:15]
    except Exception:
        return None


# ============================================================
# 顶部栏
# ============================================================

stats = fetch_ticket_stats()

# 单行顶部：标题 + 状态
tl, tr = st.columns([6, 1])
with tl:
    st.markdown(
        '<div class="app-title">'
        'LineMind'
        '<span class="badge">v4.0</span>'
        '</div>'
        '<div class="app-subtitle">企业工单管理与智能分析</div>',
        unsafe_allow_html=True,
    )
with tr:
    if HAS_API_KEY:
        st.markdown(
            '<div style="display:flex;align-items:center;justify-content:flex-end;padding-top:4px;">'
            '<span class="status-tag online"><span class="status-dot online"></span>已连接</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="display:flex;align-items:center;justify-content:flex-end;padding-top:4px;">'
            '<span class="status-tag offline"><span class="status-dot offline"></span>未连接</span>'
            '</div>',
            unsafe_allow_html=True,
        )

# ============================================================
# 统计卡片
# ============================================================

c1, c2, c3, c4 = st.columns(4)
cards = [
    ("blue",  stats["total"],      "工单总数"),
    ("amber", stats["pending"],    "待处理"),
    ("green", stats["processing"], "处理中"),
    ("red",   stats["urgent"],     "紧急工单"),
]
for col, (color, val, label) in zip([c1, c2, c3, c4], cards):
    with col:
        st.markdown(
            f'<div class="stat-card {color}">'
            f'<div class="stat-value">{val}</div>'
            f'<div class="stat-label">{label}</div></div>',
            unsafe_allow_html=True,
        )

# ============================================================
# 侧边栏
# ============================================================

with st.sidebar:
    # ⚡ 工具箱（可折叠）
    with st.expander("⚡ 工具箱", expanded=False):
        # 快捷查工单
        st.markdown('<div class="section-label">快捷查工单</div>', unsafe_allow_html=True)
        def _on_quick_ticket():
            val = st.session_state.get("_quick_ticket_input", "").strip()
            if val:
                st.session_state.pending_prompt = f"查看工单 {val} 的详细信息"
                st.session_state._quick_ticket_input = ""
        st.text_input(
            "工单编号", placeholder="WO-20260428-001...",
            label_visibility="collapsed", key="_quick_ticket_input",
            on_change=_on_quick_ticket,
        )

        # 智能提醒（v3.2: 使用 scheduler 检测逻辑）
        st.markdown('<div class="section-label">提醒</div>', unsafe_allow_html=True)
        alert_items = check_urgent_alerts()
        if not alert_items:
            # 回退到基础统计提醒
            if stats["urgent"] > 0:
                tid = stats.get("top_urgent_id", "")
                ttl = stats.get("top_urgent_title", "")
                alert_items.append({"level": "danger", "title": f'{stats["urgent"]} 个紧急工单待处理', "detail": f'{tid}: {ttl[:30]}...', "count": stats["urgent"]})
            if stats["pending"] > 5:
                alert_items.append({"level": "warning", "title": f'待处理工单积压（{stats["pending"]} 个）', "detail": "建议优先分配", "count": stats["pending"]})
            if stats["today"] > 0:
                alert_items.append({"level": "info", "title": f'今日新增 {stats["today"]} 个工单', "detail": "", "count": stats["today"]})
        if alert_items:
            for item in alert_items:
                st.markdown(
                    f'<div class="alert-badge {item["level"]}">'
                    f'<span class="dot"></span>{item["title"]}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="empty-hint">暂无提醒</div>', unsafe_allow_html=True)

        # 一键日报
        if st.button("📊 生成日报", use_container_width=True, key="_daily_report_btn"):
            report = generate_report_text(stats)
            st.session_state.pending_prompt = (
                "请基于以下数据生成一份结构化的工单日报（概览/紧急事项/处理人负荷/趋势/建议）：\n\n" + report
            )
            st.rerun()

        # v3.2 上下文状态指示器
        last_ctx = None
        for m in reversed(st.session_state.chat_history):
            if m.get("role") == "assistant" and m.get("context_info"):
                last_ctx = m["context_info"]
                break
        if last_ctx and (last_ctx.get("compressed", 0) > 0):
            total = last_ctx.get("total_messages", 0)
            compressed = last_ctx.get("compressed", 0)
            kept = last_ctx.get("kept", 0)
            st.markdown(
                f'<div class="alert-badge info" style="margin-top:6px;">'
                f'<span class="dot"></span>上下文: {total} 条消息 (早期 {compressed} 条已压缩, 保留最近 {kept} 条)</div>',
                unsafe_allow_html=True,
            )
        elif last_ctx and last_ctx.get("total_messages", 0) > 6:
            total = last_ctx.get("total_messages", 0)
            st.markdown(
                f'<div class="alert-badge info" style="margin-top:6px;">'
                f'<span class="dot"></span>上下文: {total} 条消息 (未压缩)</div>',
                unsafe_allow_html=True,
            )

        # 演示模式
        st.markdown('<div class="section-label">演示</div>', unsafe_allow_html=True)
        def _on_demo_change():
            val = st.session_state.get("_demo_select", "")
            if val != "— 演示场景 —":
                st.session_state.pending_prompt = DEMO_SCENARIOS[val]
                st.session_state._demo_select = "— 演示场景 —"
        st.selectbox(
            "场景", list(DEMO_SCENARIOS.keys()), label_visibility="collapsed",
            key="_demo_select", on_change=_on_demo_change,
        )

    # 对话历史
    st.markdown('<div class="section-label">对话历史</div>', unsafe_allow_html=True)

    if st.button("＋ 新对话", use_container_width=True):
        start_new_conversation()
        st.rerun()

    from backend.database import (
        list_conversations_grouped, delete_conversation,
        pin_conversation, unpin_conversation, update_conversation_title,
    )
    groups = list_conversations_grouped(limit=50)
    has_any = any(v for v in groups.values())

    if has_any:
        for group_name, convs in groups.items():
            if not convs:
                continue
            st.caption(group_name)
            for conv in convs:
                cid = conv["id"]
                title = conv["title"]
                preview = conv.get("preview", "")
                is_current = (cid == st.session_state.current_conversation_id)
                is_pinned = conv.get("pinned", False)

                # 截断过长标题
                short_title = title if len(title) <= 20 else title[:19] + "…"
                menu_key = f"_menu_open_{cid}"

                c_title, c_menu = st.columns([10, 1])
                with c_title:
                    label = f"▸ {short_title}" if is_current else short_title
                    btn_type = "primary" if is_current else "secondary"
                    if st.button(
                        label, key=f"h_{cid}", use_container_width=True,
                        help=title + ("\n" + preview if preview else ""),
                        type=btn_type,
                    ):
                        load_conversation_history(cid)
                        st.rerun()
                with c_menu:
                    if st.button("⋯", key=f"menu_{cid}", use_container_width=True):
                        st.session_state[menu_key] = not st.session_state.get(menu_key, False)
                        st.rerun()

                # 内联菜单
                if st.session_state.get(menu_key, False):
                    st.caption(f"**{title[:30]}{'...' if len(title)>30 else ''}**")

                    a1, a2, a3, a4, a5 = st.columns(5)
                    with a1:
                        if st.button("🤖", help="AI 生成短标题", key=f"ai_{cid}", use_container_width=True):
                            try:
                                short = _generate_short_title(title)
                                if short:
                                    update_conversation_title(cid, short)
                                    st.session_state[menu_key] = False
                                    st.rerun()
                            except Exception:
                                st.toast("AI 总结失败，请手动重命名")
                    with a2:
                        if st.button("✏️", help="重命名", key=f"rn_{cid}", use_container_width=True):
                            st.session_state[f"_rename_{cid}"] = True
                    with a3:
                        if is_pinned:
                            if st.button("📌", help="取消置顶", key=f"up_{cid}", use_container_width=True):
                                unpin_conversation(cid)
                                st.session_state[menu_key] = False
                                st.rerun()
                        else:
                            if st.button("📌", help="置顶", key=f"p_{cid}", use_container_width=True):
                                pin_conversation(cid)
                                st.session_state[menu_key] = False
                                st.rerun()
                    with a4:
                        if st.button("🗑", help="删除对话", key=f"hd_{cid}", use_container_width=True):
                            delete_conversation(cid)
                            if is_current:
                                start_new_conversation()
                            st.session_state[menu_key] = False
                            st.rerun()
                    with a5:
                        if st.button("✕", help="关闭菜单", key=f"close_{cid}", use_container_width=True):
                            st.session_state[menu_key] = False
                            st.rerun()

                    # 重命名输入框
                    if st.session_state.get(f"_rename_{cid}"):
                        new_name = st.text_input(
                            "新标题", value=title, key=f"rn_input_{cid}",
                            label_visibility="collapsed",
                        )
                        rc1, rc2 = st.columns([1, 3])
                        with rc1:
                            if st.button("确认", key=f"rn_ok_{cid}", use_container_width=True):
                                if new_name and new_name != title:
                                    update_conversation_title(cid, new_name)
                                st.session_state[f"_rename_{cid}"] = False
                                st.session_state[menu_key] = False
                                st.rerun()
                        with rc2:
                            if st.button("取消", key=f"rn_cancel_{cid}", use_container_width=True):
                                st.session_state[f"_rename_{cid}"] = False
                                st.rerun()
    else:
        st.markdown('<div class="empty-hint">暂无对话</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label">设置</div>', unsafe_allow_html=True)
    st.toggle("时间戳", key="show_timestamps")
    st.toggle("展开推理", key="auto_expand_react")
    monitor_on = st.toggle("⚡ 实时监控 (60s)", key="monitor_enabled")
    if monitor_on:
        cached = get_cached_alerts()
        last = cached.get("last_check", "尚未检测")
        st.caption(f"上次检测: {last}")
        # 每 60s 自动刷新
        st.markdown(
            '<meta http-equiv="refresh" content="60">',
            unsafe_allow_html=True,
        )

    if not HAS_API_KEY:
        api_input = st.text_input(
            "API Key", type="password", placeholder="sk-...", label_visibility="collapsed",
        )
        if api_input:
            os.environ["DEEPSEEK_API_KEY"] = api_input
            st.session_state.api_key_set = True
            st.rerun()

    with st.popover("⚙️ 数据管理", use_container_width=True):
        if st.button("🔄 重置数据", use_container_width=True):
            import sqlite3
            from backend.database import init_db as reinit_db
            conn = sqlite3.connect(settings.DATABASE_PATH)
            # v3.3: 覆盖全部 12 张表
            conn.execute("DELETE FROM quality_metrics")
            conn.execute("DELETE FROM ticket_replies")
            conn.execute("DELETE FROM tickets")
            conn.execute("DELETE FROM materials")
            conn.execute("DELETE FROM production_lines")
            conn.execute("DELETE FROM equipment")
            conn.execute("DELETE FROM conversation_messages")
            conn.execute("DELETE FROM conversations")
            conn.execute("DELETE FROM correction_rules")
            conn.execute("DELETE FROM agent_actions")
            conn.execute("DELETE FROM sql_templates")
            conn.execute("DELETE FROM db_schema_info")
            conn.commit()
            conn.close()
            reinit_db()
            start_new_conversation()
            st.success("已重置全部 12 张表")
            time.sleep(0.5)
            st.rerun()
        if st.button("🗑️ 清空历史", use_container_width=True):
            start_new_conversation()
            st.rerun()
        st.caption(f"模型: {settings.DEEPSEEK_MODEL}")

# ============================================================
# 快捷操作行
# ============================================================

btn_cols = st.columns(len(QUICK_ACTIONS))
for i, (label, prompt) in enumerate(QUICK_ACTIONS):
    with btn_cols[i]:
        if st.button(label, use_container_width=True, key=f"qb_{i}"):
            st.session_state.pending_prompt = prompt
            st.rerun()

# ============================================================
# 聊天历史
# ============================================================

for idx, msg in enumerate(st.session_state.chat_history):
    role = msg.get("role", "user")
    content = msg.get("content", "")
    msg_time = msg.get("time", "")

    with st.chat_message(role):
        st.markdown(convert_markdown_table(content))
        if role == "assistant":
            render_charts_from_steps(msg.get("steps", []))
        if st.session_state.show_timestamps and msg_time:
            # 路由徽标
            route = msg.get("route", "")
            if route:
                icon, label, color = ROUTE_LABELS.get(route, ("", route, "#8B8B8B"))
                st.markdown(
                    f'<span style="font-size:0.68rem;color:{color};margin-right:6px;">'
                    f'{icon} {label}</span>'
                    f'<span style="font-size:0.7rem;color:#6B7280;">{msg_time}</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption(msg_time)

        if role == "assistant":
            # 操作按钮行
            ac1, ac2, ac3, ac4 = st.columns([1, 1, 1, 9])
            with ac1:
                if st.button("📋 复制", key=f"c_{idx}", use_container_width=True):
                    st.session_state[f"_clip_{idx}"] = content
            with ac2:
                if st.button("📥 导出", key=f"e_{idx}", use_container_width=True):
                    st.session_state.export_target = {"content": content, "time": msg_time}
                    st.rerun()
            with ac3:
                if st.button("📝 备注", key=f"n_{idx}", use_container_width=True):
                    st.session_state.note_target = content
                    st.rerun()

            if st.session_state.get(f"_clip_{idx}"):
                st.code(content, language="markdown")
                st.caption("已复制到剪贴板区域，可手动选取")
                if st.button("✕ 关闭", key=f"cx_{idx}"):
                    del st.session_state[f"_clip_{idx}"]
                    st.rerun()

            render_reAct_steps(msg)

# ============================================================
# 备注弹窗
# ============================================================

if st.session_state.note_target:
    st.markdown("---")
    st.markdown("##### 📝 备注到工单")
    nc1, nc2 = st.columns([3, 1])
    with nc1:
        tid = st.text_input("工单编号", placeholder="TK20240501001", key="note_tid")
        ntxt = st.text_area("内容", value=st.session_state.note_target, height=100, key="note_txt")
    with nc2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✅ 确认", use_container_width=True):
            from backend.tools import add_ticket_reply
            result = add_ticket_reply(ticket_id=tid, content=ntxt)
            if result.get("success"):
                st.success(f"已备注到 {tid}")
            else:
                st.error(result.get("error", "失败"))
            st.session_state.note_target = None
            time.sleep(0.5)
            st.rerun()
        if st.button("取消", use_container_width=True):
            st.session_state.note_target = None
            st.rerun()

# ============================================================
# 导出弹窗
# ============================================================

if st.session_state.export_target:
    exp = st.session_state.export_target
    md_text = f"# 工单助手对话\n\n**{exp['time']}**\n\n---\n\n{exp['content']}"
    st.markdown("---")
    st.markdown("##### 📥 导出")
    st.code(md_text, language="markdown")
    dc1, dc2 = st.columns([1, 4])
    with dc1:
        st.download_button(
            "⬇ 下载 Markdown",
            data=md_text,
            file_name=f"ticket_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown",
        )
    with dc2:
        if st.button("关闭"):
            st.session_state.export_target = None
            st.rerun()

# ============================================================
# v4.0: 流式输出 — 桥接 async generator 到 st.write_stream
# ============================================================

def _create_stream(user_input: str, chat_history_raw: list):
    """将 graph.astream 事件转为 st.write_stream 可消费的文本流。
    Returns: (text_generator, metadata_dict)
    """
    chat_history = [
        {"role": m["role"], "content": m["content"]}
        for m in chat_history_raw
    ]

    result_queue: SyncQueue = SyncQueue()
    metadata: dict = {}
    _error: list[Exception] = []

    async def _stream():
        try:
            async for event in run_agent_stream(user_input, chat_history):
                result_queue.put(("event", event))
            result_queue.put(("done", None))
        except Exception as e:
            _error.append(e)
            result_queue.put(("error", None))

    def _run():
        asyncio.run(_stream())

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    def text_gen():
        has_tokens = False
        while True:
            kind, value = result_queue.get()
            if kind == "error":
                raise _error[0] if _error else RuntimeError("Stream error")
            if kind == "done":
                break
            if kind == "event":
                if value["type"] == "progress":
                    yield f"> {value['label']}\n\n"
                elif value["type"] == "token":
                    has_tokens = True
                    yield value["content"]
                elif value["type"] == "done":
                    metadata["output"] = value["output"]
                    metadata["steps"] = value["intermediate_steps"]
                    metadata["route"] = value["route"]
                    metadata["intent"] = value["intent"]
                    metadata["rewritten_query"] = value.get("rewritten_query", "")
                    if not has_tokens:
                        yield value["output"]

    return text_gen(), metadata


# ============================================================
# 聊天输入 + Agent
# ============================================================

prompt = None

if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if not prompt:
    prompt = st.chat_input("输入问题，例如：最近一周有哪些退款工单？")

if prompt:
    now_str = datetime.now().strftime("%m-%d %H:%M")

    with st.chat_message("user"):
        st.markdown(prompt)
        st.caption(now_str)

    if not HAS_API_KEY and not st.session_state.api_key_set:
        response_text = "请点击 ⚙️ 设置输入 DeepSeek API Key。"
        steps = []
        route = intent = rewritten = ""
        context_info = None
        with st.chat_message("assistant"):
            st.markdown(response_text)
    else:
        try:
            text_stream, metadata = _create_stream(prompt, st.session_state.chat_history)

            with st.chat_message("assistant"):
                st.write_stream(text_stream)

            response_text = metadata.get("output", "")
            steps = metadata.get("steps", [])
            route = metadata.get("route", "")
            intent = metadata.get("intent", "")
            rewritten = metadata.get("rewritten_query", "")
            context_info = None
        except Exception as e:
            response_text = f"执行出错：{str(e)}"
            steps = []
            route = intent = rewritten = ""
            context_info = None
            with st.chat_message("assistant"):
                st.markdown(response_text)

    now_assist = datetime.now().strftime("%m-%d %H:%M")

    st.session_state.chat_history.append({
        "role": "user", "content": prompt, "time": now_str, "steps": [],
    })
    st.session_state.chat_history.append({
        "role": "assistant", "content": response_text, "time": now_assist,
        "steps": steps, "route": route, "intent": intent,
        "rewritten_query": rewritten, "context_info": context_info,
    })

    save_current_conversation()
    st.rerun()
