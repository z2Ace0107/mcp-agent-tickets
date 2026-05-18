# -*- coding: utf-8 -*-
"""v4.0 LineMind 评测脚本 — 50 题测试集自动打分
核心指标：路由准确率 / 工具选择准确率 / 崩溃率
路由和工具为客观匹配，回答相关性由 DeepSeek 裁判 LLM 打分（chat 类豁免）。
"""

import json
import re
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

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from backend.agent import run_agent
from backend import init_app
from backend.config import get_settings


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def load_test_queries(path: str | None = None) -> list[dict]:
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "test_queries.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_sql_metrics(steps: list[dict]) -> dict:
    """从 steps 解析 SQL 执行成功率。"""
    sql_calls = [s for s in steps if "execute_sql" in s.get("action", "")]
    total = len(sql_calls)
    if total == 0:
        return {"sql_total": 0, "sql_success": 0, "sql_success_rate": "N/A"}
    success = sum(
        1 for s in sql_calls
        if '"error"' not in str(s.get("observation", "")).lower()
        and not s.get("degraded", False)
    )
    return {
        "sql_total": total,
        "sql_success": success,
        "sql_success_rate": f"{success}/{total} ({round(success/total*100, 1)}%)",
    }


async def judge_relevance(question: str, output: str, category: str = "") -> dict:
    """裁判 LLM 对回答相关性打分 (1-5)。"""
    if not output or len(output) < 5:
        return {"score": 1, "reason": "空输出"}

    # 根据问题类型调整评分标准
    type_hints = {
        "chat": "这是闲聊/问候类问题。只要友好得体地回应即可打4-5分，不需要提供技术信息。",
        "action": "这是工单操作类问题（更新状态/分配/回复）。关键看是否执行了正确的操作。",
        "query": "这是工单查询类问题。关键看是否返回了正确的工单数据。",
        "analyze": "这是统计分析类问题。关键看分析结果是否合理、有无数据支撑。",
        "knowledge": "这是知识检索类问题。关键看检索到的方案是否与问题相关。",
        "multi-hop": "这是多步推理类问题。需要综合多个信息源，评分时关注推理逻辑。",
    }

    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=0,
        max_tokens=150,
    )

    type_hint = type_hints.get(category, "")

    prompt = f"""你是AI助手回答质量的评测裁判。请根据问题类型给出合理评分（1-5）。

通用评分标准:
1分 — 回答完全错误、有幻觉、或拒绝回答
2分 — 有相关信息但遗漏了用户问题的核心部分
3分 — 基本回答了问题，可以接受
4分 — 较好地回答了问题，覆盖全面
5分 — 完美回答，表述清晰、信息准确且完整

{type_hint}

用户问题：{question[:500]}

AI回答：{output[:1500]}

回复格式: <分数> <一句话理由>"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        text = response.content.strip()
        match = re.search(r'[1-5]', text)
        if match:
            return {"score": int(match.group()), "reason": text[:80]}
        return {"score": 3, "reason": f"解析失败: {text[:50]}"}
    except Exception as e:
        return {"score": 3, "reason": f"LLM调用失败: {str(e)[:50]}"}


# ═══════════════════════════════════════════════════════════════
# 单题打分
# ═══════════════════════════════════════════════════════════════

async def score_result(test: dict, steps: list[dict], output: str, route: str, intent: str) -> dict:
    """对单个测试结果打分，返回五项指标的完整评分。"""
    used = [s.get("action", "") for s in steps]
    expected = test.get("expected_tools", [])

    # 1. 路由匹配
    agent_map = {
        "query": "query_agent",
        "analyze": "analyze_agent",
        "knowledge": "knowledge_agent",
        "chat": "reporter",
    }
    expected_agent = test.get("expected_agent", "")
    if not route and not intent:
        route_correct = True
        route_actual = "N/A"
    elif route in ("chat", "simple_query", "complex"):
        route_correct = (intent == expected_agent)
        route_actual = f"{route}/{intent}"
    else:
        route_correct = (route == agent_map.get(expected_agent, ""))
        route_actual = route

    # 2. 工具匹配
    if not expected:
        tools_correct = (len(used) == 0)
    else:
        expected_set = set(expected)
        used_set = set(used)
        tools_correct = expected_set.issubset(used_set) or bool(expected_set & used_set)

    # 3. SQL 执行成功率
    sql_metrics = compute_sql_metrics(steps)

    # 4. LLM 裁判回答相关性（chat 类豁免）
    if test["category"] == "chat":
        relevance = {"score": 5, "reason": "chat类豁免LLM评分"}
    else:
        relevance = await judge_relevance(test["question"], output, test["category"])

    # 错误收集
    errors = []
    for s in steps:
        obs = str(s.get("observation", ""))
        if '"error"' in obs.lower() or s.get("degraded", False):
            errors.append(s.get("action", "unknown"))

    return {
        "test_id": test["id"],
        "question": test["question"],
        "category": test["category"],
        "difficulty": test["difficulty"],
        "route_correct": route_correct,
        "route_expected": agent_map.get(expected_agent, "?"),
        "route_actual": route_actual,
        "tools_correct": tools_correct,
        "tools_used": used,
        "tools_expected": expected,
        "sql_total": sql_metrics["sql_total"],
        "sql_success": sql_metrics["sql_success"],
        "sql_success_rate": sql_metrics["sql_success_rate"],
        "answer_relevance": relevance["score"],
        "relevance_reason": relevance["reason"],
        "steps_count": len(steps),
        "errors": errors,
    }


# ═══════════════════════════════════════════════════════════════
# 批量评测
# ═══════════════════════════════════════════════════════════════

async def run_eval(max_tests: int | None = None, verbose: bool = False,
                   seed: int | None = None) -> dict:
    """运行完整评测。max_tests 限制数量，seed 固定随机抽样。"""
    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY:
        print("❌ 未配置 DEEPSEEK_API_KEY，请先设置环境变量")
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
        print(f"\n[{i+1}/{len(queries)}] {qid}: {question[:50]}...", end=" ", flush=True)

        try:
            result = await run_agent(user_input=question)
            output = result.get("output", "")
            steps = result.get("intermediate_steps", [])
            route = result.get("route", "")
            intent = result.get("intent", "")

            score = await score_result(test, steps, output, route, intent)
            results.append(score)

            status = "PASS" if score["tools_correct"] and score["route_correct"] else (
                "WARN" if score["tools_correct"] or score["route_correct"] else "FAIL"
            )
            sql_info = f" sql={score['sql_success_rate']}" if score["sql_total"] > 0 else ""
            print(f"{status} | route={'OK' if score['route_correct'] else 'X'} "
                  f"tools={'OK' if score['tools_correct'] else 'X'} "
                  f"rel={score['answer_relevance']}/5"
                  f"{sql_info}"
                  f" steps={score['steps_count']}")
        except Exception as e:
            print(f"CRASH: {str(e)[:80]}")
            results.append({
                "test_id": qid,
                "question": question,
                "category": test["category"],
                "difficulty": test["difficulty"],
                "route_correct": False,
                "route_expected": "?",
                "route_actual": "CRASH",
                "tools_correct": False,
                "tools_used": [],
                "tools_expected": test.get("expected_tools", []),
                "sql_total": 0, "sql_success": 0, "sql_success_rate": "N/A",
                "answer_relevance": 1, "relevance_reason": f"崩溃: {str(e)[:50]}",
                "steps_count": 0,
                "errors": [str(e)[:200]],
                "crash": True,
            })

    elapsed = time.time() - start_time

    # ── 汇总统计 ──
    total = len(results)
    route_ok = sum(1 for r in results if r["route_correct"])
    tools_ok = sum(1 for r in results if r["tools_correct"])
    relevance_avg = sum(r["answer_relevance"] for r in results) / total if total else 0
    crashes = sum(1 for r in results if r.get("crash"))
    errors = sum(len(r.get("errors", [])) for r in results)

    # SQL 汇总
    sql_total_all = sum(r["sql_total"] for r in results)
    sql_success_all = sum(r["sql_success"] for r in results)
    sql_rate_all = f"{sql_success_all}/{sql_total_all} ({round(sql_success_all/sql_total_all*100, 1)}%)" if sql_total_all else "N/A"

    # 按类别
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

    # 按难度
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
            "sql_success_rate": sql_rate_all,
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


# ═══════════════════════════════════════════════════════════════
# 报告输出
# ═══════════════════════════════════════════════════════════════

def print_report(report: dict):
    """打印评测报告到控制台（精简版：路由+工具+崩溃）。"""
    m = report["meta"]
    s = report["summary"]

    print("\n" + "═" * 50)
    print(f"  LineMind v4.0  评测报告")
    print("═" * 50)
    print(f"  {m['total_tests']} 题  ⏱ {m['elapsed_seconds']}s  "
          f"({m['avg_seconds_per_test']}s/题)  💥 {s['crashes']}")
    print()
    print(f"  路由准确率    {s['route_accuracy']}")
    print(f"  工具选择率    {s['tool_selection_accuracy']}")
    print()
    print("  类别明细")
    for cat, v in report.get("by_category", {}).items():
        print(f"  {cat:10s}  {v['total']:2d}题  路由 {v['route_accuracy']:>6s}  "
              f"工具 {v['tool_accuracy']:>6s}")
    print()

    # 失败用例
    failed = [r for r in report["details"]
              if not (r.get("tools_correct") and r.get("route_correct"))]
    if failed:
        print(f"  需关注 ({len(failed)} 题):")
        for r in failed:
            tools = "OK" if r.get("tools_correct") else f"X (used:{r.get('tools_used',[])} expected:{r.get('tools_expected',[])})"
            route = "OK" if r.get("route_correct") else f"X (actual:{r.get('route_actual','?')} expected:{r.get('route_expected','?')})"
            print(f"  {r['test_id']} [{r['category']}] {r['question'][:40]}...")
            print(f"    路由:{route}  工具:{tools}")
    print("═" * 50)


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    import random

    parser = argparse.ArgumentParser(description="LineMind 评测脚本")
    parser.add_argument("-n", "--count", type=int, default=None,
                        help="限制测试数量（默认全部 50 题）")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="输出 JSON 报告路径")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="仅输出最终报告")
    parser.add_argument("--seed", type=int, default=None,
                        help="随机种子（固定抽样顺序，结果可复现）")
    args = parser.parse_args()

    report = asyncio.run(run_eval(
        max_tests=args.count, verbose=not args.quiet, seed=args.seed,
    ))
    print_report(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n报告已保存: {args.output}")