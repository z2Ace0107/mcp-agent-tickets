# -*- coding: utf-8 -*-
"""Agentic Trace Viewer — 查看、分析 Agent 执行轨迹。

Usage:
    python backend/trace_viewer.py              # 列出最近 20 条 trace
    python backend/trace_viewer.py <trace_id>   # 查看单条 trace 详情
    python backend/trace_viewer.py --stats <N>  # 统计最近 N 条 trace
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import list_agent_traces, get_agent_trace, get_connection


def _fmt_ms(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"


def list_traces(limit: int = 20):
    traces = list_agent_traces(limit)
    if not traces:
        print("(暂无 trace 记录)")
        return

    print(f"{'trace_id':>10s}  {'时间':<16s}  {'步数':>4s}  {'延迟':>6s}  {'回答':>5s}  {'压缩':>4s}  问题")
    print("-" * 120)
    for t in traces:
        q = t["question"].replace("\n", " ")[:50]
        print(
            f"{t['trace_id']:>10s}  {t['created_at'][:16]:<16s}  "
            f"{t['total_steps']:>4d}  {_fmt_ms(t['total_latency_ms']):>6s}  "
            f"{t['final_answer_length']:>5d}  "
            f"{'是' if t['context_compressed'] else '否':>4s}   {q}"
        )


def show_trace(trace_id: str):
    trace = get_agent_trace(trace_id)
    if not trace:
        print(f"找不到 trace: {trace_id}")
        return

    print(f"{'='*60}")
    print(f"Trace: {trace['trace_id']}")
    print(f"时间:    {trace['created_at']}")
    print(f"问题:    {trace['question']}")
    print(f"步数:    {trace['total_steps']}  |  迭代: {trace['total_iterations']}")
    print(f"延迟:    {_fmt_ms(trace['total_latency_ms'])}")
    print(f"回答:    {trace['final_answer_length']} 字符")
    print(f"停止:    {trace['stop_reason']}")
    print(f"压缩:    {'是' if trace['context_compressed'] else '否'}  |  消息数: {trace['context_total_messages']}")
    print(f"额度:    {'已耗尽' if trace['go_quota_exhausted'] else '正常'}")

    steps = trace.get("steps", [])
    if not steps:
        print("\n(无工具调用步骤)")
        return

    print(f"\n{'─'*60}")
    print(f"工具调用步骤 ({len(steps)}):")
    for s in steps:
        verdict_icon = {"ok": "✓", "error": "✗", "empty": "○", "duplicate": "↻"}.get(
            s["observation_verdict"], "?"
        )
        print(f"  {verdict_icon} [{s['step_index']}] {s['tool_name']}  ({_fmt_ms(s['elapsed_ms'])})")
        print(f"       {s['observation_summary']}")
        if s["tool_args"]:
            try:
                args = json.loads(s["tool_args"])
                if args:
                    print(f"       参数: {json.dumps(args, ensure_ascii=False)[:120]}")
            except Exception:
                pass


def show_stats(limit: int = 50):
    traces = list_agent_traces(limit)
    if not traces:
        print("(暂无 trace 记录)")
        return

    total = len(traces)
    steps_total = sum(t["total_steps"] for t in traces)
    avg_steps = steps_total / total
    avg_latency = sum(t["total_latency_ms"] for t in traces) / total
    compressed = sum(1 for t in traces if t["context_compressed"])
    quota = sum(1 for t in traces if t["go_quota_exhausted"])

    stop_reasons: dict[str, int] = {}
    for t in traces:
        reason = t["stop_reason"] or "unknown"
        stop_reasons[reason] = stop_reasons.get(reason, 0) + 1

    step_ranges = {"0": 0, "1-2": 0, "3-5": 0, "6+": 0}
    for t in traces:
        s = t["total_steps"]
        if s == 0:
            step_ranges["0"] += 1
        elif s <= 2:
            step_ranges["1-2"] += 1
        elif s <= 5:
            step_ranges["3-5"] += 1
        else:
            step_ranges["6+"] += 1

    print(f"Trace 统计 (最近 {total} 条)")
    print(f"{'─'*50}")
    print(f"总 trace 数:   {total}")
    print(f"总工具步数:    {steps_total}")
    print(f"平均步数:      {avg_steps:.1f}")
    print(f"平均延迟:      {_fmt_ms(int(avg_latency))}")
    print(f"上下文压缩:    {compressed}/{total} ({compressed * 100 // total}%)")
    print(f"额度耗尽:      {quota}/{total} ({quota * 100 // total}%)")

    print(f"\n停止原因分布:")
    for reason, count in sorted(stop_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason:<30s} {count:>3d} ({count * 100 // total}%)")

    print(f"\n步数分布:")
    for label, count in step_ranges.items():
        bar = "█" * (count * 20 // total) if total > 0 else ""
        print(f"  {label:<6s} {count:>3d} ({count * 100 // total}%) {bar}")

    # 工具使用频率
    tool_counts: dict[str, int] = {}
    for t in traces:
        detail = get_agent_trace(t["trace_id"])
        if detail:
            for s in detail.get("steps", []):
                name = s["tool_name"]
                tool_counts[name] = tool_counts.get(name, 0) + 1

    if tool_counts:
        print(f"\n工具使用频率:")
        for name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
            print(f"  {name:<35s} {count:>3d}")


if __name__ == "__main__":
    argv = sys.argv[1:]

    if not argv:
        list_traces()
    elif argv[0] == "--stats":
        n = int(argv[1]) if len(argv) > 1 else 50
        show_stats(n)
    elif argv[0] == "--recent":
        n = int(argv[1]) if len(argv) > 1 else 20
        list_traces(n)
    elif argv[0].startswith("--"):
        list_traces()
    else:
        show_trace(argv[0])
