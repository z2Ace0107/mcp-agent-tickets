# -*- coding: utf-8 -*-
"""v5.0 LineMind 评测脚本 — 全客观指标，零 LLM 消耗

指标：
- 路由准确率：Supervisor 是否正确分类
- 工具 Jaccard：工具选择与预期的交集/并集比（0-1）
- 工具执行成功率：调用是否返回 error 或触发降级
- 效率：平均步数 + 工具调用次数 + 单题耗时
- 崩溃率
"""

import json
import sys
import os
import io
import time
import asyncio
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from backend.agent import run_agent
from backend import init_app
from backend.config import get_settings


# ═══════════════════════════════════════════════════════════════
# 指标函数
# ═══════════════════════════════════════════════════════════════

AGENT_MAP = {
    "query": "query_agent", "analyze": "analyze_agent",
    "knowledge": "knowledge_agent", "chat": "reporter",
}


def load_test_queries(path: str | None = None) -> list[dict]:
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "test_queries.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def jaccard(a: set, b: set) -> float:
    """Jaccard 相似系数。0=无重叠，1=完全一致。"""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def tool_exec_success(steps: list[dict]) -> tuple[int, int]:
    """统计工具调用成功率。"""
    calls = [s for s in steps if s.get("action")]
    if not calls:
        return 0, 0
    ok = sum(1 for c in calls
             if not c.get("degraded")
             and '"error"' not in str(c.get("observation", "")).lower())
    return len(calls), ok


def score_result(test: dict, steps: list[dict], route: str, intent: str) -> dict:
    """单题评分——全客观。"""
    used = [s.get("action", "") for s in steps]
    expected = test.get("expected_tools", [])
    expected_agent = test.get("expected_agent", "")
    expected_route = AGENT_MAP.get(expected_agent, "?")

    # 路由
    route_ok = (route == expected_route) if route else (
        (AGENT_MAP.get(intent, "") == expected_route) if intent else False)

    # 工具 Jaccard
    jac = jaccard(set(expected), set(used))

    # 工具执行成功率
    tc, ok = tool_exec_success(steps)

    # 错误收集
    errors = [s.get("action", "?") for s in steps
              if s.get("degraded") or '"error"' in str(s.get("observation", "")).lower()]

    return {
        "test_id": test["id"], "question": test["question"],
        "category": test["category"], "difficulty": test["difficulty"],
        "route_correct": route_ok,
        "route_expected": expected_route, "route_actual": route or intent or "N/A",
        "tool_jaccard": round(jac, 2),
        "tool_pass": jac >= 0.5,
        "tools_used": used, "tools_expected": expected,
        "tool_calls_total": tc, "tool_calls_ok": ok,
        "steps_count": len(steps),
        "errors": errors,
    }


# ═══════════════════════════════════════════════════════════════
# 批量评测
# ═══════════════════════════════════════════════════════════════

async def run_eval(max_tests: int | None = None, seed: int | None = None) -> dict:
    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY:
        print("❌ 未配置 DEEPSEEK_API_KEY")
        return {"error": "no api key"}

    init_app()
    queries = load_test_queries()
    if max_tests and max_tests < len(queries):
        import random as _random
        rng = _random.Random(seed) if seed is not None else _random.Random()
        rng.shuffle(queries)
        queries = queries[:max_tests]

    results = []
    start_time = time.time()

    for i, test in enumerate(queries):
        qid = test["id"]
        question = test["question"]
        t0 = time.perf_counter()
        print(f"[{i+1}/{len(queries)}] {qid}: {question[:50]}...", end=" ", flush=True)

        try:
            result = await run_agent(user_input=question)
            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            steps = result.get("intermediate_steps", [])
            route = result.get("route", "")
            intent = result.get("intent", "")

            score = score_result(test, steps, route, intent)
            score["elapsed_ms"] = elapsed_ms
            results.append(score)

            status = "PASS" if score["route_correct"] and score["tool_pass"] else (
                "WARN" if score["route_correct"] or score["tool_pass"] else "FAIL")
            print(f"{status} route={'OK' if score['route_correct'] else 'X'} "
                  f"jac={score['tool_jaccard']:.2f} "
                  f"exec={score['tool_calls_ok']}/{score['tool_calls_total']} "
                  f"steps={score['steps_count']}")
        except Exception as e:
            print(f"CRASH: {str(e)[:80]}")
            results.append({
                "test_id": qid, "question": question,
                "category": test["category"], "difficulty": test["difficulty"],
                "route_correct": False, "route_expected": "?",
                "route_actual": "CRASH",
                "tool_jaccard": 0.0, "tool_pass": False,
                "tools_used": [], "tools_expected": test.get("expected_tools", []),
                "tool_calls_total": 0, "tool_calls_ok": 0,
                "steps_count": 0,
                "errors": [str(e)[:200]],
                "crash": True,
            })

    elapsed = time.time() - start_time

    # ── 汇总 ──
    crashes = sum(1 for r in results if r.get("crash"))
    valid = [r for r in results if not r.get("crash")]
    n = len(valid) or 1

    route_ok = sum(r["route_correct"] for r in valid)
    tool_pass = sum(r["tool_pass"] for r in valid)
    jac_avg = sum(r["tool_jaccard"] for r in valid) / n
    step_avg = sum(r["steps_count"] for r in valid) / n
    ms_avg = sum(r.get("elapsed_ms", 0) for r in valid) / n
    tc = sum(r["tool_calls_total"] for r in valid)
    to = sum(r["tool_calls_ok"] for r in valid)
    errs = sum(len(r.get("errors", [])) for r in valid)

    # 按类别
    by_cat = {}
    for r in valid:
        c = r["category"]
        if c not in by_cat:
            by_cat[c] = {"n": 0, "route": 0, "tp": 0, "jac": 0.0, "ms": 0}
        by_cat[c]["n"] += 1
        by_cat[c]["route"] += r["route_correct"]
        by_cat[c]["tp"] += r["tool_pass"]
        by_cat[c]["jac"] += r["tool_jaccard"]
        by_cat[c]["ms"] += r.get("elapsed_ms", 0)

    # 按难度
    by_diff = {}
    for r in valid:
        d = r["difficulty"]
        if d not in by_diff:
            by_diff[d] = {"n": 0, "route": 0, "tp": 0}
        by_diff[d]["n"] += 1
        by_diff[d]["route"] += r["route_correct"]
        by_diff[d]["tp"] += r["tool_pass"]

    report = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(results),
            "elapsed_seconds": round(elapsed, 1),
            "avg_seconds_per_test": round(elapsed / len(results), 1) if results else 0,
        },
        "summary": {
            "route_accuracy": f"{route_ok}/{n} ({round(route_ok/n*100, 1)}%)",
            "avg_tool_jaccard": round(jac_avg, 2),
            "tool_pass_rate": f"{tool_pass}/{n} ({round(tool_pass/n*100, 1)}%)",
            "tool_exec_success": f"{to}/{tc} ({round(to/tc*100, 1)}%)" if tc else "N/A",
            "avg_steps": round(step_avg, 1),
            "avg_ms_per_test": round(ms_avg, 0),
            "crashes": crashes,
            "tool_errors_in_steps": errs,
        },
        "by_category": {
            c: {
                "total": v["n"],
                "route": f"{v['route']}/{v['n']} ({round(v['route']/v['n']*100, 1)}%)",
                "tool_jaccard": round(v["jac"] / v["n"], 2),
                "tool_pass": f"{v['tp']}/{v['n']} ({round(v['tp']/v['n']*100, 1)}%)",
                "avg_ms": round(v["ms"] / v["n"], 0),
            }
            for c, v in sorted(by_cat.items())
        },
        "by_difficulty": {
            d: {
                "total": v["n"],
                "route": f"{v['route']}/{v['n']} ({round(v['route']/v['n']*100, 1)}%)",
                "tool_pass": f"{v['tp']}/{v['n']} ({round(v['tp']/v['n']*100, 1)}%)",
            }
            for d, v in sorted(by_diff.items())
        },
        "details": results,
    }
    return report


# ═══════════════════════════════════════════════════════════════
# 报告输出
# ═══════════════════════════════════════════════════════════════

def print_report(report: dict):
    m = report["meta"]
    s = report["summary"]

    print("\n" + "═" * 55)
    print(f"  LineMind v5.0 评测  {m['total_tests']}题 ⏱{m['elapsed_seconds']}s "
          f"💥{s['crashes']}")
    print("═" * 55)
    print(f"  路由准确率      {s['route_accuracy']}")
    print(f"  工具 Jaccard    {s['avg_tool_jaccard']}  (1=完全匹配)")
    print(f"  工具通过率      {s['tool_pass_rate']}  (Jaccard≥0.5)")
    print(f"  工具执行成功率  {s['tool_exec_success']}")
    print(f"  平均步数/耗时   {s['avg_steps']}步 / {s['avg_ms_per_test']}ms")
    print(f"  工具异常        {s['tool_errors_in_steps']}")
    print()

    print(f"  {'类别':10s} {'题':>3s} {'路由':>10s} {'Jac':>6s} {'工具通过':>10s} {'耗时':>6s}")
    print(f"  {'─'*10} {'─'*3} {'─'*10} {'─'*6} {'─'*10} {'─'*6}")
    for cat, v in report.get("by_category", {}).items():
        print(f"  {cat:10s} {v['total']:3d}  {v['route']:10s} {v['tool_jaccard']:>5}  {v['tool_pass']:10s} {v['avg_ms']:>4}ms")
    print()

    failed = [r for r in report["details"]
              if not r.get("crash") and (not r["route_correct"] or not r["tool_pass"])]
    if failed:
        print(f"  需关注 ({len(failed)} 题):")
        for r in failed:
            route = "OK" if r["route_correct"] else f"X(→{r.get('route_actual','?')}, want {r.get('route_expected','?')})"
            tool = f"jac={r['tool_jaccard']:.2f} (used:{r['tools_used']} want:{r['tools_expected']})"
            print(f"  {r['test_id']} [{r['category']}/{r['difficulty']}] {r['question'][:45]}...")
            print(f"    路由:{route}  工具:{tool}")
    print("═" * 55)


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LineMind 评测（全客观，零 LLM 消耗）")
    parser.add_argument("-n", "--count", type=int, default=None, help="测试数量（默认全部 50 题）")
    parser.add_argument("-o", "--output", type=str, default=None, help="JSON 报告输出路径")
    parser.add_argument("--seed", type=int, default=None, help="随机种子（固定抽样，结果可复现）")
    args = parser.parse_args()

    report = asyncio.run(run_eval(max_tests=args.count, seed=args.seed))
    print_report(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n报告已保存: {args.output}")
