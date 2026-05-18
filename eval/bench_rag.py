# -*- coding: utf-8 -*-
"""RAG 双通道检索对比评测 — 向量单通道 vs 双通道(向量+FTS5) RRF融合

指标:
- MRR (Mean Reciprocal Rank): 第一个正确结果排名倒数的平均值
- Hit@K: Top-K 结果中至少命中一条正确结果的比例

用法:
    python eval/bench_rag.py
    python eval/bench_rag.py --json   # 输出 JSON 格式
"""

import io
import json
import os
import sys
import time
import argparse
from collections import defaultdict

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from backend.database import init_db
from backend.rag import (
    index_solved_tickets,
    search_solutions,
    RRF_K,
    _rrf_fusion,
    _keyword_search,
    _rewrite_query,
    get_collection,
    COLLECTION_NAME,
)

# ═══════════════════════════════════════════════════════════════
# 标注测试集 — 15 条查询
# ═══════════════════════════════════════════════════════════════

ANNOTATED_QUERIES = [
    # ── 直接匹配 (含英文术语，关键词通道优势) ──────────────
    {
        "id": "R01",
        "query": "CNC主轴异响怎么处理",
        "expected": ["WO-20260428-001"],
        "note": "英文缩写CNC，FTS5关键词通道能直接命中",
    },
    {
        "id": "R02",
        "query": "AGV搬运车导航偏差怎么修的",
        "expected": ["WO-20260420-004"],
        "note": "英文缩写AGV/SLAM，FTS5关键词通道优势",
    },
    {
        "id": "R03",
        "query": "SMT回流焊温度曲线漂移虚焊率高",
        "expected": ["WO-20260422-016"],
        "note": "英文缩写SMT/BGA/QFP，双通道各自命中",
    },
    # ── 直接匹配 (纯中文，两通道表现接近) ────────────────
    {
        "id": "R04",
        "query": "电镀件盐雾试验出现锈点",
        "expected": ["WO-20260425-008"],
        "note": "纯中文语义匹配",
    },
    {
        "id": "R05",
        "query": "冲压车间安全光幕被短接",
        "expected": ["WO-20260503-010"],
        "note": "纯中文精确描述",
    },
    {
        "id": "R06",
        "query": "叉车充电区通风系统故障氢气积聚",
        "expected": ["WO-20260430-012"],
        "note": "含元素名氢气，中文场景",
    },
    {
        "id": "R07",
        "query": "冷却循环水藻类滋生换热效率下降",
        "expected": ["WO-20260427-020"],
        "note": "纯中文环境监测类",
    },
    {
        "id": "R08",
        "query": "数控磨床砂轮动平衡失效表面振纹",
        "expected": ["WO-20260511-023"],
        "note": "中文技术术语，向量通道",
    },
    # ── 同义/变体匹配 ──────────────────────────────────────
    {
        "id": "R09",
        "query": "主轴轴承磨损需要更换",
        "expected": ["WO-20260428-001"],
        "note": "同义改写 — 没说CNC，用轴承磨损替代异响",
    },
    {
        "id": "R10",
        "query": "AGV撞到东西了",
        "expected": ["WO-20260420-004"],
        "note": "口语化描述，关键字少，考验语义检索",
    },
    {
        "id": "R11",
        "query": "电路板BGA虚焊",
        "expected": ["WO-20260422-016"],
        "note": "用BGA/虚焊替代回流焊温度异常，含英文缩写",
    },
    {
        "id": "R12",
        "query": "防爆排风机不转了",
        "expected": ["WO-20260430-012"],
        "note": "口语化改写 — 用风机不转替代通风系统故障",
    },
    {
        "id": "R13",
        "query": "钝化膜不致密导致生锈",
        "expected": ["WO-20260425-008"],
        "note": "技术细节改写 — 用钝化膜替代电镀件盐雾",
    },
    {
        "id": "R14",
        "query": "氢气浓度报警怎么处理",
        "expected": ["WO-20260430-012"],
        "note": "用氢气浓度替代叉车充电区",
    },
    # ── 干扰查询：无精确匹配 ──────────────────────────────
    {
        "id": "R15",
        "query": "喷涂机械臂定位不准漆膜厚度不均",
        "expected": [],
        "note": "相关工单为处理中状态，不在已解决索引中。预期无高置信结果",
    },
]


# ═══════════════════════════════════════════════════════════════
# 评测核心
# ═══════════════════════════════════════════════════════════════

def vector_only_search(query: str, n_results: int = 10) -> list[dict]:
    """单通道：仅 ChromaDB 向量检索（模拟旧版行为）。"""
    collection = get_collection()
    rewritten = _rewrite_query(query)

    if collection.count() == 0:
        return []

    results = collection.query(query_texts=[rewritten], n_results=n_results)

    output = []
    if results["documents"] and results["documents"][0]:
        for i in range(len(results["documents"][0])):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            output.append({
                "ticket_id": meta.get("ticket_id", ""),
                "title": meta.get("title", ""),
                "similarity": round(1.0 / (1.0 + distance), 4),
                "source": "vector",
            })
    return output


def dual_channel_search(query: str, n_results: int = 10) -> list[dict]:
    """双通道：向量 + FTS5 → RRF 融合（当前实现）。"""
    collection = get_collection()
    rewritten = _rewrite_query(query)

    if collection.count() == 0:
        return []

    fetch_k = n_results * 3

    # 向量通道
    v_results = collection.query(query_texts=[rewritten], n_results=fetch_k)
    vector_results = []
    if v_results["documents"] and v_results["documents"][0]:
        for i in range(len(v_results["documents"][0])):
            meta = v_results["metadatas"][0][i]
            distance = v_results["distances"][0][i]
            vector_results.append({
                "ticket_id": meta.get("ticket_id", ""),
                "title": meta.get("title", ""),
                "description": v_results["documents"][0][i],
                "solution": meta.get("solution", ""),
                "distance": distance,
                "similarity": round(1.0 / (1.0 + distance), 4),
                "source": "vector",
            })

    # 关键词通道
    keyword_results = _keyword_search(rewritten, fetch_k)

    # RRF 融合
    fused = _rrf_fusion(vector_results, keyword_results, n_results)

    if not fused and vector_results:
        fused = [
            {
                "ticket_id": r["ticket_id"],
                "title": r["title"],
                "description": r["description"],
                "solution": r["solution"],
                "similarity": r["similarity"],
                "rrf_score": 0,
                "sources": ["vector"],
            }
            for r in vector_results[:n_results]
        ]

    return fused


def compute_mrr(results: list[dict], expected: list[str]) -> float:
    """计算 MRR (Mean Reciprocal Rank)。"""
    if not expected:
        return 1.0  # 无正确答案 = 完美（只需不高置信返回）
    for rank, item in enumerate(results, start=1):
        if item["ticket_id"] in expected:
            return 1.0 / rank
    return 0.0


def compute_hit_at_k(results: list[dict], expected: list[str], k: int) -> bool:
    """检查 Top-K 中是否至少命中一条。"""
    if not expected:
        return True
    top_k_ids = {r["ticket_id"] for r in results[:k]}
    return bool(top_k_ids & set(expected))


def check_negative_query(results: list[dict], threshold: float = 0.8) -> bool:
    """干扰查询检查：Top-1 相似度不应过高（说明没被误导）。"""
    if not results:
        return True
    return results[0]["similarity"] < threshold


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

def run_benchmark(json_output: bool = False) -> dict:
    """运行对比评测。"""
    # 确保索引就绪
    init_db()
    index_solved_tickets()
    collection = get_collection()
    total_indexed = collection.count()

    if not json_output:
        print(f"{'='*65}")
        print(f"  LineMind RAG 双通道对比评测")
        print(f"  已索引工单: {total_indexed} 条 | 测试查询: {len(ANNOTATED_QUERIES)} 条")
        print(f"  RRF k={RRF_K}")
        print(f"{'='*65}\n")

    results = {
        "indexed_tickets": total_indexed,
        "num_queries": len(ANNOTATED_QUERIES),
        "rrf_k": RRF_K,
        "queries": [],
        "summary": {},
    }

    # 累计指标
    vector_mrr_sum = 0.0
    dual_mrr_sum = 0.0
    vector_hit1 = vector_hit3 = vector_hit5 = 0
    dual_hit1 = dual_hit3 = dual_hit5 = 0
    dual_fusion_wins = 0
    vector_only_wins = 0
    ties = 0
    negative_passed = 0
    negative_total = 0
    vector_sim_sum = 0.0
    dual_sim_sum = 0.0
    dual_source_both = 0  # 双通道同时贡献的查询数
    valid_query_count = 0

    for item in ANNOTATED_QUERIES:
        qid = item["id"]
        query = item["query"]
        expected = item["expected"]
        note = item["note"]
        is_negative = len(expected) == 0

        # 执行两路检索
        t0 = time.perf_counter()
        v_results = vector_only_search(query, n_results=10)
        t_vector = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        d_results = dual_channel_search(query, n_results=10)
        t_dual = (time.perf_counter() - t0) * 1000

        # 计算指标
        v_mrr = compute_mrr(v_results, expected)
        d_mrr = compute_mrr(d_results, expected)
        v_h1 = compute_hit_at_k(v_results, expected, 1)
        v_h3 = compute_hit_at_k(v_results, expected, 3)
        v_h5 = compute_hit_at_k(v_results, expected, 5)
        d_h1 = compute_hit_at_k(d_results, expected, 1)
        d_h3 = compute_hit_at_k(d_results, expected, 3)
        d_h5 = compute_hit_at_k(d_results, expected, 5)

        vector_mrr_sum += v_mrr
        dual_mrr_sum += d_mrr
        vector_hit1 += v_h1
        vector_hit3 += v_h3
        vector_hit5 += v_h5
        dual_hit1 += d_h1
        dual_hit3 += d_h3
        dual_hit5 += d_h5

        if d_mrr > v_mrr:
            dual_fusion_wins += 1
        elif v_mrr > d_mrr:
            vector_only_wins += 1
        else:
            ties += 1

        if is_negative:
            negative_total += 1
            if check_negative_query(d_results):
                negative_passed += 1

        # 置信度（Top-1 相似度）
        v_sim = v_results[0]["similarity"] if v_results else 0
        d_sim = d_results[0]["similarity"] if d_results else 0
        if not is_negative and v_results:
            valid_query_count += 1
            vector_sim_sum += v_sim
            dual_sim_sum += d_sim
            d_src = d_results[0].get("sources", []) if d_results else []
            if len(d_src) >= 2:
                dual_source_both += 1

        # 打印行
        if not json_output:
            v_top = v_results[0]["ticket_id"] if v_results else "-"
            d_top = d_results[0]["ticket_id"] if d_results else "-"
            d_src_str = "+".join(d_results[0].get("sources", ["?"])) if d_results else "-"
            v_flag = "✓" if v_h1 else ("△" if v_h3 else "✗")
            d_flag = "✓" if d_h1 else ("△" if d_h3 else "✗")
            sim_delta = d_sim - v_sim
            sim_str = f"↑+{sim_delta:.3f}" if sim_delta > 0.001 else (f"↓{sim_delta:.3f}" if sim_delta < -0.001 else "=")

            print(
                f"{qid} [{v_flag}→{d_flag}] sim: {v_sim:.3f}→{d_sim:.3f} {sim_str} | "
                f"双通道[{d_src_str}] | {note[:40]}"
            )

        # 记录详情
        results["queries"].append({
            "id": qid,
            "query": query,
            "expected": expected,
            "note": note,
            "is_negative": is_negative,
            "vector": {
                "mrr": round(v_mrr, 4),
                "hit1": v_h1, "hit3": v_h3, "hit5": v_h5,
                "top3": [r["ticket_id"] for r in v_results[:3]],
                "top3_sim": [r["similarity"] for r in v_results[:3]],
                "time_ms": round(t_vector, 2),
            },
            "dual": {
                "mrr": round(d_mrr, 4),
                "hit1": d_h1, "hit3": d_h3, "hit5": d_h5,
                "top3": [r["ticket_id"] for r in d_results[:3]],
                "top3_sim": [r["similarity"] for r in d_results[:3]],
                "top3_sources": [
                    "+".join(r.get("sources", ["?"])) for r in d_results[:3]
                ],
                "time_ms": round(t_dual, 2),
            },
        })

    # 计算平均置信度
    avg_v_sim = round(vector_sim_sum / valid_query_count, 4) if valid_query_count else 0
    avg_d_sim = round(dual_sim_sum / valid_query_count, 4) if valid_query_count else 0

    # 汇总
    n = len(ANNOTATED_QUERIES)
    summary = {
        "vector_channel": {
            "mrr": round(vector_mrr_sum / n, 4),
            "hit@1": f"{vector_hit1}/{n} ({round(vector_hit1/n*100, 1)}%)",
            "hit@3": f"{vector_hit3}/{n} ({round(vector_hit3/n*100, 1)}%)",
            "hit@5": f"{vector_hit5}/{n} ({round(vector_hit5/n*100, 1)}%)",
            "avg_confidence": avg_v_sim,
        },
        "dual_channel": {
            "mrr": round(dual_mrr_sum / n, 4),
            "hit@1": f"{dual_hit1}/{n} ({round(dual_hit1/n*100, 1)}%)",
            "hit@3": f"{dual_hit3}/{n} ({round(dual_hit3/n*100, 1)}%)",
            "hit@5": f"{dual_hit5}/{n} ({round(dual_hit5/n*100, 1)}%)",
            "avg_confidence": avg_d_sim,
        },
        "comparison": {
            "mrr_improvement": f"{(dual_mrr_sum - vector_mrr_sum) / vector_mrr_sum * 100:.1f}%"
            if vector_mrr_sum > 0 else "N/A",
            "confidence_boost": f"{(avg_d_sim - avg_v_sim) / avg_v_sim * 100:.1f}%"
            if avg_v_sim > 0 else "N/A",
            "dual_source_queries": f"{dual_source_both}/{valid_query_count}",
            "dual_wins": dual_fusion_wins,
            "vector_wins": vector_only_wins,
            "ties": ties,
        },
    }

    if negative_total > 0:
        summary["negative_query_pass"] = f"{negative_passed}/{negative_total}"

    results["summary"] = summary

    if not json_output:
        print(f"\n{'='*70}")
        print(f"  评测汇总")
        print(f"{'='*70}")
        print(f"  {'指标':<16} {'向量单通道':<24} {'双通道(RRF)':<24}")
        print(f"  {'-'*64}")
        print(f"  {'MRR':<16} {summary['vector_channel']['mrr']:<24} {summary['dual_channel']['mrr']:<24}")
        print(f"  {'Hit@1':<16} {summary['vector_channel']['hit@1']:<24} {summary['dual_channel']['hit@1']:<24}")
        print(f"  {'Hit@3':<16} {summary['vector_channel']['hit@3']:<24} {summary['dual_channel']['hit@3']:<24}")
        print(f"  {'Hit@5':<16} {summary['vector_channel']['hit@5']:<24} {summary['dual_channel']['hit@5']:<24}")
        print(f"  {'平均置信度':<16} {summary['vector_channel']['avg_confidence']:<24} {summary['dual_channel']['avg_confidence']:<24}")
        print(f"  {'-'*64}")
        print(f"  置信度提升: {summary['comparison']['confidence_boost']}")
        print(f"  双通道共同贡献: {summary['comparison']['dual_source_queries']} 条查询")
        print(f"  双通道胜: {dual_fusion_wins}  向量胜: {vector_only_wins}  平: {ties}")
        if negative_total > 0:
            print(f"  干扰查询通过: {summary['negative_query_pass']}")
        print(f"{'='*70}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG 双通道检索对比评测")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("-o", "--output", type=str, default=None, help="结果写入 JSON 文件")
    args = parser.parse_args()

    result = run_benchmark(json_output=args.json)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.output:
        out_path = args.output
        if 'summary' not in result:
            # 重新运行获取完整结果
            pass
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n结果已写入: {out_path}")
