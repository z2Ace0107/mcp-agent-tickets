# -*- coding: utf-8 -*-
"""v3.4 LineMind LLM-as-a-judge 评测脚本 — 50 题测试集自动打分"""

import json
import time
import asyncio
import sys
import os
import io
from datetime import datetime

# Windows GBK 兼容：强制 stdout 使用 UTF-8
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


def score_result(test: dict, steps: list[dict], output: str, route: str, intent: str) -> dict:
    """对单个测试结果打分。

    Returns:
        {
            "test_id": str,
            "question": str,
            "route_correct": bool,
            "tools_correct": bool,
            "tools_used": [str],
            "tools_expected": [str],
            "answer_relevance": int (1-5, estimated),
            "steps_count": int,
            "errors": [str],
        }
    """
    used = [s.get("action", "") for s in steps]
    expected = test.get("expected_tools", [])
    expected_agent = test.get("expected_agent", "")

    # 路由匹配（兼容 v2.0/v3.2/v4.0 不同返回格式）
    agent_map = {
        "query": "query_agent",
        "analyze": "analyze_agent",
        "knowledge": "knowledge_agent",
        "chat": "reporter",
    }
    expected_agent = test.get("expected_agent", "")
    # v2.0: 无 route 无 intent → 无法评判路由，一律算对（纯工具评测）
    if not route and not intent:
        route_correct = True
    # v3.2: route 是 chat/simple_query/complex，用 intent 判断
    elif route in ("chat", "simple_query", "complex"):
        route_correct = (intent == expected_agent)
    # v4.0: route 是 agent 节点名
    else:
        route_correct = (route == agent_map.get(expected_agent, ""))

    # 工具匹配
    if not expected:
        tools_correct = (len(used) == 0)
    else:
        expected_set = set(expected)
        used_set = set(used)
        tools_correct = expected_set.issubset(used_set) or bool(expected_set & used_set)

    # 相关性预估（基于是否有合理steps和输出长度）
    if not output or len(output) < 5:
        relevance = 1
    elif tools_correct and route_correct and len(output) > 50:
        relevance = 5
    elif tools_correct or route_correct:
        relevance = 3 if len(output) > 30 else 2
    else:
        relevance = 2 if len(output) > 20 else 1

    # 错误检测
    errors = []
    for s in steps:
        obs = str(s.get("observation", ""))
        if '"error"' in obs.lower() or '"degraded": true' in obs.lower():
            errors.append(s.get("action", "unknown"))

    return {
        "test_id": test["id"],
        "question": test["question"],
        "category": test["category"],
        "difficulty": test["difficulty"],
        "route_correct": route_correct,
        "route_expected": agent_map.get(expected_agent, "?"),
        "route_actual": route,
        "tools_correct": tools_correct,
        "tools_used": used,
        "tools_expected": expected,
        "answer_relevance": relevance,
        "steps_count": len(steps),
        "errors": errors,
    }


async def run_eval(max_tests: int | None = None, verbose: bool = False) -> dict:
    """运行完整评测。

    Args:
        max_tests: 限制测试数量（None=全部）
        verbose: 打印每条结果
    """
    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY:
        print("❌ 未配置 DEEPSEEK_API_KEY，请先设置环境变量")
        return {"error": "no api key"}

    init_app()
    queries = load_test_queries()
    if max_tests:
        queries = queries[:max_tests]

    results = []
    start_time = time.time()

    for i, test in enumerate(queries):
        qid = test["id"]
        question = test["question"]
        print(f"\n[{i+1}/{len(queries)}] {qid}: {question[:50]}...", end=" ", flush=True)

        try:
            result = await run_agent(user_input=question)
            output = result.get("output", "")
            steps = result.get("intermediate_steps", [])
            route = result.get("route", "")
            intent = result.get("intent", "")

            score = score_result(test, steps, output, route, intent)
            results.append(score)

            status = "PASS" if score["tools_correct"] and score["route_correct"] else (
                "WARN" if score["tools_correct"] or score["route_correct"] else "FAIL"
            )
            print(f"{status} | route={'OK' if score['route_correct'] else 'X'} "
                  f"tools={'OK' if score['tools_correct'] else 'X'} "
                  f"rel={score['answer_relevance']}/5 "
                  f"steps={score['steps_count']}")
        except Exception as e:
            print(f"CRASH: {str(e)[:80]}")
            results.append({
                "test_id": qid,
                "question": question,
                "category": test["category"],
                "difficulty": test["difficulty"],
                "route_correct": False,
                "tools_correct": False,
                "tools_used": [],
                "tools_expected": test.get("expected_tools", []),
                "answer_relevance": 1,
                "steps_count": 0,
                "errors": [str(e)[:200]],
                "crash": True,
            })

    elapsed = time.time() - start_time

    # 汇总统计
    total = len(results)
    route_ok = sum(1 for r in results if r["route_correct"])
    tools_ok = sum(1 for r in results if r["tools_correct"])
    relevance_avg = sum(r["answer_relevance"] for r in results) / total if total else 0
    crashes = sum(1 for r in results if r.get("crash"))
    errors = sum(len(r.get("errors", [])) for r in results)

    # 按类别统计
    by_category = {}
    for r in results:
        cat = r["category"]
        if cat not in by_category:
            by_category[cat] = {"total": 0, "tools_ok": 0, "route_ok": 0, "relevance_sum": 0}
        by_category[cat]["total"] += 1
        if r["tools_correct"]:
            by_category[cat]["tools_ok"] += 1
        if r["route_correct"]:
            by_category[cat]["route_ok"] += 1
        by_category[cat]["relevance_sum"] += r["answer_relevance"]

    # 按难度统计
    by_difficulty = {}
    for r in results:
        diff = r["difficulty"]
        if diff not in by_difficulty:
            by_difficulty[diff] = {"total": 0, "tools_ok": 0, "route_ok": 0}
        by_difficulty[diff]["total"] += 1
        if r["tools_correct"]:
            by_difficulty[diff]["tools_ok"] += 1
        if r["route_correct"]:
            by_difficulty[diff]["route_ok"] += 1

    report = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total,
            "elapsed_seconds": round(elapsed, 1),
            "avg_seconds_per_test": round(elapsed / total, 1) if total else 0,
        },
        "summary": {
            "route_accuracy": f"{route_ok}/{total} ({round(route_ok/total*100, 1)}%)" if total else "N/A",
            "tool_selection_accuracy": f"{tools_ok}/{total} ({round(tools_ok/total*100, 1)}%)" if total else "N/A",
            "avg_answer_relevance": f"{round(relevance_avg, 1)}/5",
            "crashes": crashes,
            "tool_errors": errors,
        },
        "by_category": {
            cat: {
                "total": v["total"],
                "tool_accuracy": f"{round(v['tools_ok']/v['total']*100, 1)}%" if v["total"] else "N/A",
                "route_accuracy": f"{round(v['route_ok']/v['total']*100, 1)}%" if v["total"] else "N/A",
                "avg_relevance": f"{round(v['relevance_sum']/v['total'], 1)}/5" if v["total"] else "N/A",
            }
            for cat, v in sorted(by_category.items())
        },
        "by_difficulty": {
            diff: {
                "total": v["total"],
                "tool_accuracy": f"{round(v['tools_ok']/v['total']*100, 1)}%" if v["total"] else "N/A",
                "route_accuracy": f"{round(v['route_ok']/v['total']*100, 1)}%" if v["total"] else "N/A",
            }
            for diff, v in sorted(by_difficulty.items())
        },
        "details": results,
    }

    return report


def print_report(report: dict):
    """打印评测报告到控制台。"""
    m = report["meta"]
    s = report["summary"]

    print("\n" + "=" * 60)
    print("  LineMind v3.4 — 评测报告")
    print("=" * 60)
    print(f"  时间: {m['timestamp']}")
    print(f"  测试数: {m['total_tests']}  耗时: {m['elapsed_seconds']}s  "
          f"平均: {m['avg_seconds_per_test']}s/题")
    print()
    print("  【总体指标】")
    print(f"  Agent 路由准确率:    {s['route_accuracy']}")
    print(f"  工具选择准确率:       {s['tool_selection_accuracy']}")
    print(f"  平均回答相关性:       {s['avg_answer_relevance']}")
    print(f"  崩溃数: {s['crashes']}  工具错误: {s['tool_errors']}")
    print()
    print("  【按类别】")
    for cat, v in report.get("by_category", {}).items():
        print(f"  {cat:12s}  ({v['total']:2d}题)  路由:{v['route_accuracy']:>7s}  "
              f"工具:{v['tool_accuracy']:>7s}  相关:{v['avg_relevance']}")
    print()
    print("  【按难度】")
    for diff, v in report.get("by_difficulty", {}).items():
        print(f"  {diff:6s}  ({v['total']:2d}题)  路由:{v['route_accuracy']:>7s}  "
              f"工具:{v['tool_accuracy']:>7s}")
    print()

    # 失败用例
    failed = [r for r in report["details"]
              if not (r["tools_correct"] and r["route_correct"])]
    if failed:
        print(f"  【需关注 ({len(failed)} 题)】")
        for r in failed:
            tools = "OK" if r["tools_correct"] else f"X (used:{r['tools_used']} expected:{r['tools_expected']})"
            route = "OK" if r["route_correct"] else f"X (actual:{r['route_actual']} expected:{r.get('route_expected','?')})"
            print(f"  {r['test_id']} [{r['category']}/{r['difficulty']}] {r['question'][:45]}...")
            print(f"         路由:{route}  工具:{tools}  相关:{r['answer_relevance']}/5")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LineMind 评测脚本")
    parser.add_argument("-n", "--count", type=int, default=None,
                        help="限制测试数量（默认全部）")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="输出 JSON 报告路径")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="仅输出最终报告")
    args = parser.parse_args()

    report = asyncio.run(run_eval(max_tests=args.count, verbose=not args.quiet))
    print_report(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n报告已保存: {args.output}")
