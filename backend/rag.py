# -*- coding: utf-8 -*-
"""RAG模块 — 基于 ChromaDB 的工单解决方案向量检索

Embedding 策略：使用阿里云百炼 API（OpenAI 兼容格式）。
本地 sentence-transformers 代码以注释形式保留在文件末尾供参考。
"""

from typing import Any

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from chromadb.config import Settings as ChromaSettings
from openai import OpenAI

from backend.config import get_settings
from backend.logger import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "ticket_solutions"


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
# 索引与检索
# ============================================================

def index_solved_tickets() -> int:
    """将数据库中所有「已解决」工单索引到 ChromaDB。

    Returns:
        已索引的工单数量。
    """
    from backend.database import get_solved_tickets_db

    tickets = get_solved_tickets_db()
    if not tickets:
        logger.warning("没有已解决的工单可供索引")
        return 0

    collection = get_collection()

    # 清空旧索引（全量重建）
    try:
        existing_ids = collection.get()["ids"]
        if existing_ids:
            collection.delete(ids=existing_ids)
    except Exception:
        pass

    # 构建文档：标题 + 描述 + 解决方案（供向量检索）
    documents = [
        f"{t['title']}\n{t['description']}\n解决方案：{t['solution']}"
        for t in tickets
    ]
    ids = [t["ticket_id"] for t in tickets]
    metadatas = [
        {"ticket_id": t["ticket_id"], "type": t["type"], "title": t["title"], "solution": t["solution"]}
        for t in tickets
    ]

    collection.add(documents=documents, ids=ids, metadatas=metadatas)
    logger.info(f"已索引 {len(tickets)} 条已解决工单")
    return len(tickets)


def search_solutions(query: str, n_results: int = 3) -> dict[str, Any]:
    """搜索历史解决方案。

    Args:
        query: 用户描述的问题文本。
        n_results: 返回最大结果数，默认 3。

    Returns:
        {
            "query": str,
            "results": [{"similarity": float, "ticket_id": str, "title": str, "description": str, "solution": str}, ...]
        }
    """
    collection = get_collection()

    if collection.count() == 0:
        return {"query": query, "results": [], "message": "暂无已解决工单可参考，请先运行索引"}

    results = collection.query(query_texts=[query], n_results=n_results)

    formatted = []
    for i in range(len(results["documents"][0])):
        doc = results["documents"][0][i]
        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        similarity = round(1.0 / (1.0 + distance), 4)

        formatted.append({
            "similarity": similarity,
            "ticket_id": metadata.get("ticket_id", ""),
            "title": metadata.get("title", ""),
            "description": doc,
            "solution": metadata.get("solution", ""),
        })

    return {
        "query": query,
        "results": formatted,
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
