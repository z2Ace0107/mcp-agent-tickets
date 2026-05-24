# -*- coding: utf-8 -*-
"""RAG模块 — 双通道混合检索（向量语义 + FTS5 关键词 → RRF 融合）

架构:
- 向量通道: ChromaDB 语义检索（阿里百炼 Embedding）
- 关键词通道: SQLite FTS5 全文索引（英文/数字前缀匹配 + 中文 LIKE 兜底）
- RRF 融合: Reciprocal Rank Fusion (k=60)

Embedding 策略：使用阿里云百炼 API（OpenAI 兼容格式）。
本地 sentence-transformers 代码以注释形式保留在文件末尾供参考。
"""

import re
import sqlite3
from collections import defaultdict
from typing import Any

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI

from backend.config import get_settings
from backend.database import get_connection
from backend.logger import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "ticket_solutions"
RRF_K = 60  # RRF 融合常数

# ── 查询改写：口语填充词 ──────────────────────────────────────
_QUERY_FILLERS = [
    "上次那个", "我记得有个", "之前遇到过", "帮我查一下", "帮我查查",
    "我想找", "有没有", "怎么修的", "怎么解决的", "怎么处理",
    "那个问题", "之前那个", "好像有个", "大概是一个", "记不清了",
    "那个", "这个", "有个", "一种", "怎么",
]


# ============================================================
# DeepSeek Embedding 函数
# ============================================================

class BailianEmbeddingFunction(EmbeddingFunction):
    """使用阿里云百炼 API 生成文本嵌入向量（OpenAI 兼容格式）。"""

    def __init__(self) -> None:
        s = get_settings()
        self._client = OpenAI(
            api_key=s.EMBEDDING_API_KEY,
            base_url=s.EMBEDDING_BASE_URL,
        )
        self._model = s.EMBEDDING_MODEL

    def __call__(self, input: Documents) -> Embeddings:
        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=input,
            )
            return [d.embedding for d in response.data]
        except Exception as e:
            logger.error(f"Embedding API 调用失败: {str(e)}")
            raise RuntimeError(f"Embedding 不可用: {str(e)}")


# ============================================================
# ChromaDB 集合管理
# ============================================================

def _get_client() -> chromadb.PersistentClient:
    """获取 ChromaDB 持久化客户端。"""
    settings = get_settings()
    return chromadb.PersistentClient(
        path=settings.CHROMA_PERSIST_DIR,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_collection() -> chromadb.Collection:
    """获取或创建 ChromaDB 集合。"""
    client = _get_client()
    embedding_fn = BailianEmbeddingFunction()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )


# ============================================================
# 索引
# ============================================================

def index_solved_tickets() -> int:
    """将数据库中所有「已解决」工单索引到 ChromaDB 和 FTS5。

    Returns:
        已索引的工单数量。
    """
    from backend.database import get_solved_tickets_db

    tickets = get_solved_tickets_db()
    if not tickets:
        logger.warning("没有已解决的工单可供索引")
        return 0

    # ── ChromaDB 向量索引 ─────────────────────────────────────
    collection = get_collection()
    try:
        existing_ids = collection.get()["ids"]
        if existing_ids:
            collection.delete(ids=existing_ids)
    except Exception:
        pass

    documents = [
        f"{t['title']}\n{t['description']}\n解决方案：{t['solution']}"
        for t in tickets
    ]
    ids = [t["ticket_id"] for t in tickets]
    metadatas = [
        {"ticket_id": t["ticket_id"], "type": t["type"], "title": t["title"], "solution": t["solution"]}
        for t in tickets
    ]

    batch_size = 10
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i : i + batch_size]
        batch_ids = ids[i : i + batch_size]
        batch_metas = metadatas[i : i + batch_size]
        collection.add(documents=batch_docs, ids=batch_ids, metadatas=batch_metas)

    # ── FTS5 全文索引 ─────────────────────────────────────────
    _rebuild_fts(tickets)

    logger.info(f"已索引 {len(tickets)} 条已解决工单（向量 + FTS5）")
    return len(tickets)


# ============================================================
# FTS5 关键词通道
# ============================================================

def _ensure_fts_table() -> None:
    """确保 FTS5 表存在（兼容旧数据库迁移）。"""
    conn = get_connection()
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS tickets_fts USING fts5(title, description, solution)"
        )
        conn.commit()
    finally:
        conn.close()


def _rebuild_fts(tickets: list[dict]) -> None:
    """从已解决工单列表全量重建 FTS5 索引。"""
    _ensure_fts_table()
    conn = get_connection()
    try:
        conn.execute("DELETE FROM tickets_fts")
        for t in tickets:
            conn.execute(
                "INSERT INTO tickets_fts(rowid, title, description, solution) "
                "VALUES (?, ?, ?, ?)",
                (t["id"], t["title"], t["description"], t["solution"]),
            )
        conn.commit()
    finally:
        conn.close()


def _rewrite_query(query_text: str) -> str:
    """去除口语化填充词，提取技术关键词。"""
    cleaned = query_text.strip()
    for f in _QUERY_FILLERS:
        cleaned = cleaned.replace(f, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else query_text.strip()


def _build_fts_query(query_text: str) -> str | None:
    """构建 FTS5 查询语法。纯中文查询返回 None（走 LIKE 兜底）。"""
    ascii_words = re.findall(r"[a-zA-Z0-9]{2,}", query_text)
    return " OR ".join(f'"{w}"*' for w in ascii_words[:10]) if ascii_words else None


def _keyword_search(query_text: str, fetch_k: int) -> list[dict]:
    """FTS5 关键词检索 + 中文 LIKE 兜底。"""
    _ensure_fts_table()
    conn = get_connection()
    try:
        rows = []
        fts_query = _build_fts_query(query_text)

        if fts_query:
            rows = conn.execute(
                "SELECT f.rowid, t.ticket_id, t.title, t.description, t.solution, "
                "       -f.rank AS score "
                "FROM tickets_fts f "
                "JOIN tickets t ON f.rowid = t.id "
                "WHERE tickets_fts MATCH ? "
                "ORDER BY f.rank LIMIT ?",
                (fts_query, fetch_k),
            ).fetchall()

        # 中文 LIKE 兜底：用正则提取中文字符序列（2字以上）
        cn_tokens = re.findall(r"[一-鿿]{2,}", query_text)
        if cn_tokens:
            like_parts = " OR ".join(
                "(t.title LIKE ? OR t.description LIKE ? OR t.solution LIKE ?)"
                for _ in cn_tokens
            )
            params: list[Any] = []
            for t in cn_tokens:
                params.extend([f"%{t}%", f"%{t}%", f"%{t}%"])

            like_rows = conn.execute(
                f"SELECT t.id AS rowid, t.ticket_id, t.title, t.description, "
                f"       t.solution, 1.0 AS score "
                f"FROM tickets t "
                f"WHERE t.status = '已解决' AND ({like_parts}) "
                f"LIMIT ?",
                params + [fetch_k],
            ).fetchall()

            seen = {r["rowid"] for r in rows}
            for lr in like_rows:
                if lr["rowid"] not in seen:
                    rows.append(lr)
                    seen.add(lr["rowid"])

        rows = sorted(rows, key=lambda r: r["score"], reverse=True)[:fetch_k]

        return [
            {
                "ticket_id": r["ticket_id"],
                "title": r["title"],
                "description": r["description"],
                "solution": r["solution"],
                "bm25_rank": i + 1,
                "source": "keyword",
            }
            for i, r in enumerate(rows)
        ]
    finally:
        conn.close()


# ============================================================
# RRF 融合
# ============================================================

def _rrf_fusion(
    vector_results: list[dict],
    keyword_results: list[dict],
    k: int,
) -> list[dict]:
    """RRF (Reciprocal Rank Fusion) 融合两路检索结果。

    公式: RRF(d) = Σ 1 / (k + rank_i(d))
    """
    scores: dict[str, float] = defaultdict(float)
    doc_info: dict[str, dict] = {}

    for rank, item in enumerate(vector_results, start=1):
        tid = item["ticket_id"]
        scores[tid] += 1.0 / (RRF_K + rank)
        if tid not in doc_info:
            doc_info[tid] = item

    for rank, item in enumerate(keyword_results, start=1):
        tid = item["ticket_id"]
        scores[tid] += 1.0 / (RRF_K + rank)
        if tid not in doc_info:
            doc_info[tid] = item

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:k]

    result = []
    for tid in sorted_ids:
        info = doc_info[tid]
        srcs = _get_sources(tid, vector_results, keyword_results)
        # 相似度：单通道用原始分，双通道给 20% boost
        base_sim = info.get("similarity", 0.5)
        if len(srcs) >= 2:
            base_sim = min(base_sim * 1.25, 1.0)
        result.append({
            "ticket_id": tid,
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "solution": info.get("solution", ""),
            "similarity": round(base_sim, 4),
            "rrf_score": round(scores[tid], 6),
            "sources": srcs,
        })
    return result


def _get_sources(tid: str, vector: list[dict], keyword: list[dict]) -> list[str]:
    """判断结果来自哪些通道。"""
    srcs = []
    if any(item["ticket_id"] == tid for item in vector):
        srcs.append("vector")
    if any(item["ticket_id"] == tid for item in keyword):
        srcs.append("keyword")
    return srcs


# ============================================================
# 双通道混合检索
# ============================================================

def search_solutions(query: str, n_results: int = 3) -> dict[str, Any]:
    """双通道混合检索：向量语义 + FTS5 关键词 → RRF 融合排序。

    Args:
        query: 用户描述的问题文本。
        n_results: 返回最大结果数，默认 3。

    Returns:
        {
            "query": str,
            "results": [{"similarity": float, "ticket_id": str, "title": str,
                          "description": str, "solution": str, "sources": [...], ...}],
            "_debug": {...},
        }
    """
    collection = get_collection()

    if collection.count() == 0:
        return {"query": query, "results": [], "message": "暂无已解决工单可参考，请先运行索引"}

    rewritten = _rewrite_query(query)
    fetch_k = n_results * 3

    # ── 通道一: 向量语义检索 ──────────────────────────────────
    chroma_results = collection.query(query_texts=[rewritten], n_results=fetch_k)

    vector_results = []
    if chroma_results["documents"] and chroma_results["documents"][0]:
        for i in range(len(chroma_results["documents"][0])):
            meta = chroma_results["metadatas"][0][i]
            distance = chroma_results["distances"][0][i]
            vector_results.append({
                "ticket_id": meta.get("ticket_id", ""),
                "title": meta.get("title", ""),
                "description": chroma_results["documents"][0][i],
                "solution": meta.get("solution", ""),
                "distance": distance,
                "similarity": round(1.0 / (1.0 + distance), 4),
                "source": "vector",
            })

    # ── 通道二: FTS5 关键词检索 ───────────────────────────────
    keyword_results = _keyword_search(rewritten, fetch_k)

    # ── RRF 融合 ─────────────────────────────────────────────
    fused = _rrf_fusion(vector_results, keyword_results, n_results)

    # 融合后回退：RRF 无结果时使用向量结果
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

    return {
        "query": query,
        "results": fused,
        "_debug": {
            "rewritten_query": rewritten,
            "vector_count": len(vector_results),
            "keyword_count": len(keyword_results),
        },
    }


# ============================================================
# 备用方案：本地 sentence-transformers（注释保留）
#
# 若 DeepSeek 不支持 embedding 端点，可取消下方注释启用本地模型：
#
# from sentence_transformers import SentenceTransformer
#
# class LocalEmbeddingFunction(EmbeddingFunction):
#     def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
#         self._model = SentenceTransformer(model_name)
#
#     def __call__(self, input: Documents) -> Embeddings:
#         return self._model.encode(input).tolist()
#
# 然后将 get_collection() 中的 DeepSeekEmbeddingFunction()
# 替换为 LocalEmbeddingFunction() 即可。
# ============================================================
