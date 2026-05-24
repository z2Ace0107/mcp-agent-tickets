# -*- coding: utf-8 -*-
"""v5.1 LineMind 评测 — 全客观指标 + 任务完成度

指标：
- 必要工具覆盖率：required_tools 被调用占比（0-1）
- 工具执行成功率：调用是否返回 error 或触发降级
- 步数分布：min_steps/max_steps 范围内占比
- 任务完成度：综合评分（必要工具 + 步数 + 无错误）
- 崩溃率
"""
from __future__ import annotations

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


def load_test_queries(path: str | None = None) -> list[dict]:
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "test_queries.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def tool_exec_success(steps: list[dict]) -> tuple[int, int]:
    calls = [s for s in steps if s.get("action")]
    if not calls:
        return 0, 0
    ok = sum(1 for c in calls
             if not c.get("degraded")
             and '"error"' not in str(c.get("observation", "")).lower())
    return len(calls), ok


def score_result(test: dict, steps: list[dict]) -> dict:
    used = [s.get("action", "") for s in steps]
    used_set = set(used)
    required = test.get("required_tools", [])
    optional = test.get("optional_tools", [])
    min_steps = test.get("min_steps", 0)
    max_steps = test.get("max_steps", 99)

    required_set = set(required)
    allowed_set = required_set | set(optional)

    required_covered = len(required_set & used_set) / len(required_set) if required_set else 1.0
    suspicious = [t for t in used_set if t not in allowed_set and t]

    step_count = len(steps)
    steps_in_range = min_steps <= step_count <= max_steps

    tc, ok = tool_exec_success(steps)

    completion_score = 0.0
    if required_covered >= 1.0:
        completion_score += 0.4
    if steps_in_range:
        completion_score += 0.3
    if ok == tc and tc > 0:
        completion_score += 0.3
    elif tc == 0 and len(required) == 0:
        completion_score += 0.3

    errors = [s.get("action", "?") for s in steps
              if s.get("degraded") or '"error"' in str(s.get("observation", "")).lower()]

    return {
        "test_id": test["id"],
        "question": test["question"],
        "category": test["category"],
        "difficulty": test["difficulty"],
        "required_coverage": round(required_covered, 2),
        "required_pass": required_covered >= 1.0,
        "suspicious_tools": suspicious,
        "steps_in_range": steps_in_range,
        "min_steps": min_steps,
        "max_steps": max_steps,
        "task_completion": round(completion_score, 2),
        "tools_used": used,
        "tools_required": required,
        "tools_optional": optional,
        "tool_calls_total": tc,
        "tool_calls_ok": ok,
        "steps_count": step_count,
        "errors": errors,
    }


async def run_eval(max_tests: int | None = None, seed: int | None = None) -> dict:
    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY:
        print("\u274c 未配置 DEEPSEEK_API_KEY")
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
            trace_id = result.get("trace_id", "")

            score = score_result(test, steps)
            score["elapsed_ms"] = elapsed_ms
            score["trace_id"] = trace_id
            results.append(score)

            status = "PASS" if score["required_pass"] else "WARN"
            print(f"{status} cover={score['required_coverage']:.2f} "
                  f"steps={score['steps_count']}/{score['min_steps']}-{score['max_steps']} "
                  f"comp={score['task_completion']:.2f} "
                  f"exec={score['tool_calls_ok']}/{score['tool_calls_total']}")
        except Exception as e:
            print(f"CRASH: {str(e)[:80]}")
            results.append({
                "test_id": qid,
                "question": question,
                "category": test["category"],
                "difficulty": test["difficulty"],
                "required_coverage": 0.0,
                "required_pass": False,
                "suspicious_tools": [],
                "steps_in_range": False,
                "min_steps": test.get("min_steps", 0),
                "max_steps": test.get("max_steps", 0),
                "task_completion": 0.0,
                "tools_used": [],
                "tools_required": test.get("required_tools", []),
                "tools_optional": test.get("optional_tools", []),
                "tool_calls_total": 0,
                "tool_calls_ok": 0,
                "steps_count": 0,
                "errors": [str(e)[:200]],
                "crash": True,
            })

    elapsed = time.time() - start_time

    crashes = sum(1 for r in results if r.get("crash"))
    valid = [r for r in results if not r.get("crash")]
    n = len(valid) or 1

    required_ok = sum(r["required_pass"] for r in valid)
    comp_avg = sum(r["task_completion"] for r in valid) / n
    in_range_count = sum(r["steps_in_range"] for r in valid)
    step_avg = sum(r["steps_count"] for r in valid) / n
    ms_avg = sum(r.get("elapsed_ms", 0) for r in valid) / n
    tc = sum(r["tool_calls_total"] for r in valid)
    to = sum(r["tool_calls_ok"] for r in valid)
    errs = sum(len(r.get("errors", [])) for r in valid)
    suspicious_total = sum(len(r.get("suspicious_tools", [])) for r in valid)

    step_dist = {"0": 0, "1-2": 0, "3-5": 0, "6+": 0}
    for r in valid:
        sc = r["steps_count"]
        if sc == 0:
            step_dist["0"] += 1
        elif sc <= 2:
            step_dist["1-2"] += 1
        elif sc <= 5:
            step_dist["3-5"] += 1
        else:
            step_dist["6+"] += 1

    by_cat = {}
    for r in valid:
        c = r["category"]
        if c not in by_cat:
            by_cat[c] = {"n": 0, "rp": 0, "comp": 0.0, "step": 0.0, "ms": 0.0}
        by_cat[c]["n"] += 1
        by_cat[c]["rp"] += r["required_pass"]
        by_cat[c]["comp"] += r["task_completion"]
        by_cat[c]["step"] += r["steps_count"]
        by_cat[c]["ms"] += r.get("elapsed_ms", 0)

    by_diff = {}
    for r in valid:
        d = r["difficulty"]
        if d not in by_diff:
            by_diff[d] = {"n": 0, "rp": 0, "comp": 0.0}
        by_diff[d]["n"] += 1
        by_diff[d]["rp"] += r["required_pass"]
        by_diff[d]["comp"] += r["task_completion"]

    report = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(results),
            "elapsed_seconds": round(elapsed, 1),
            "avg_seconds_per_test": round(elapsed / len(results), 1) if results else 0,
        },
        "summary": {
            "required_tool_pass": f"{required_ok}/{n} ({round(required_ok/n*100, 1)}%)",
            "avg_task_completion": round(comp_avg, 2),
            "steps_in_range": f"{in_range_count}/{n} ({round(in_range_count/n*100, 1)}%)",
            "tool_exec_success": f"{to}/{tc} ({round(to/tc*100, 1)}%)" if tc else "N/A",
            "avg_steps": round(step_avg, 1),
            "avg_ms_per_test": round(ms_avg, 0),
            "crashes": crashes,
            "tool_errors": errs,
            "suspicious_tool_calls": suspicious_total,
            "step_distribution": step_dist,
            "traced_runs": sum(1 for r in valid if r.get("trace_id")),
        },
        "by_category": {
            c: {
                "total": v["n"],
                "required_pass": f"{v['rp']}/{v['n']} ({round(v['rp']/v['n']*100, 1)}%)",
                "avg_completion": round(v["comp"] / v["n"], 2),
                "avg_steps": round(v["step"] / v["n"], 1),
                "avg_ms": round(v["ms"] / v["n"], 0),
            }
            for c, v in sorted(by_cat.items())
        },
        "by_difficulty": {
            d: {
                "total": v["n"],
                "required_pass": f"{v['rp']}/{v['n']} ({round(v['rp']/v['n']*100, 1)}%)",
                "avg_completion": round(v["comp"] / v["n"], 2),
            }
            for d, v in sorted(by_diff.items())
        },
        "details": results,
    }
    return report


def print_report(report: dict):
    m = report["meta"]
    s = report["summary"]

    print("\n" + "\u2550" * 60)
    print(f"  LineMind v5.1 \u8bc4\u6d4b  {m['total_tests']}\u9898 \u23f1{m['elapsed_seconds']}s "
          f"\u2728{s['crashes']} crash")
    print("\u2550" * 60)
    print(f"  \u5fc5\u8981\u5de5\u5177\u8986\u76d6\u7387   {s['required_tool_pass']}")
    print(f"  \u4efb\u52a1\u5b8c\u6210\u5ea6       {s['avg_task_completion']}  (0-1, \u8d8a\u9ad8\u8d8a\u597d)")
    print(f"  \u6b65\u6570\u8303\u56f4\u5185        {s['steps_in_range']}")
    print(f"  \u5de5\u5177\u6267\u884c\u6210\u529f\u7387   {s['tool_exec_success']}")
    print(f"  \u5e73\u5747\u6b65\u6570/\u8017\u65f6     {s['avg_steps']}\u6b65 / {s['avg_ms_per_test']}ms")
    print(f"  \u5de5\u5177\u5f02\u5e38          {s['tool_errors']}")
    print(f"  \u53ef\u7591\u5de5\u5177\u8c03\u7528      {s['suspicious_tool_calls']}")
    print(f"  \u6b65\u6570\u5206\u5e03          0: {s['step_distribution']['0']}  "
          f"1-2: {s['step_distribution']['1-2']}  "
          f"3-5: {s['step_distribution']['3-5']}  "
          f"6+: {s['step_distribution']['6+']}")
    if s.get("traced_runs"):
        print(f"  \u5df2\u8bb0\u5f55 Trace       {s['traced_runs']} \u6761")
    print()

    print(f"  {'\u7c7b\u522b':12s} {'\u9898':>3s} {'\u5fc5\u8981\u8986\u76d6':>10s} {'\u5b8c\u6210\u5ea6':>7s} {'\u6b65\u6570':>5s} {'\u8017\u65f6':>6s}")
    print(f"  {'\u2500'*12} {'\u2500'*3} {'\u2500'*10} {'\u2500'*7} {'\u2500'*5} {'\u2500'*6}")
    for cat, v in report.get("by_category", {}).items():
        print(f"  {cat:12s} {v['total']:3d}  {v['required_pass']:10s} {v['avg_completion']:>6} {v['avg_steps']:>4} {v['avg_ms']:>5}ms")
    print()

    failed = [r for r in report["details"]
              if not r.get("crash") and (not r["required_pass"] or not r["steps_in_range"])]
    if failed:
        print(f"  \u9700\u5173\u6ce8 ({len(failed)} \u9898):")
        for r in failed:
            cover = f"cover={r['required_coverage']:.2f} (need:{r['tools_required']} used:{r['tools_used']})"
            step_info = f"steps={r['steps_count']}/{r['min_steps']}-{r['max_steps']}"
            print(f"  {r['test_id']} [{r['category']}/{r['difficulty']}] {r['question'][:45]}...")
            print(f"     {cover}  {step_info}")
            if r.get("suspicious_tools"):
                print(f"     \u53ef\u7591\u5de5\u5177: {r['suspicious_tools']}")

    print("\u2550" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LineMind v5.1 \u8bc4\u6d4b")
    parser.add_argument("-n", "--count", type=int, default=None, help="\u6d4b\u8bd5\u6570\u91cf\uff08\u9ed8\u8ba4\u5168\u90e8 50 \u9898\uff09")
    parser.add_argument("-o", "--output", type=str, default=None, help="JSON \u62a5\u544a\u8f93\u51fa\u8def\u5f84")
    parser.add_argument("--seed", type=int, default=None, help="\u968f\u673a\u79cd\u5b50")
    args = parser.parse_args()

    report = asyncio.run(run_eval(max_tests=args.count, seed=args.seed))
    print_report(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n\u62a5\u544a\u5df2\u4fdd\u5b58: {args.output}")
