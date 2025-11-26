# rag_service.py
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Type, TYPE_CHECKING
from types import TracebackType

import chromadb
from chromadb.config import Settings
import requests
from requests.exceptions import RequestException, Timeout

import knowledge
from knowledge import CorpusItem

# [关键修改] 解决循环引用：只在类型检查时导入 DataProcessor
if TYPE_CHECKING:
    from data_processor import DataProcessor

logger = logging.getLogger(__name__)


# ===========================
# Embedding 客户端
# ===========================


class EmbeddingClient:
    """
    简单的 Embedding 客户端，调用 OpenAI/ECNU 兼容的 /embeddings 接口。
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        *,
        timeout: int = 30,
        max_batch_size: int = 100,
    ) -> None:
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.timeout = timeout
        self.max_batch_size = max_batch_size

        if not self.base_url:
            logger.warning("EmbeddingClient: 未配置 OPENAI_BASE_URL")
        if not self.api_key:
            logger.warning("EmbeddingClient: 未配置 OPENAI_API_KEY")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        为多条文本生成向量，支持自动分批处理。
        """
        if not texts:
            return []

        if not self.base_url or not self.api_key:
            raise RuntimeError("EmbeddingClient: base_url 或 api_key 未配置")

        all_vectors: List[List[float]] = []
        total_texts = len(texts)

        for i in range(0, total_texts, self.max_batch_size):
            batch_texts = texts[i : i + self.max_batch_size]
            try:
                batch_vectors = self._request_embeddings(batch_texts)
                all_vectors.extend(batch_vectors)
            except Exception as e:
                logger.error(f"Batch embedding failed at index {i}: {e}")
                raise

        return all_vectors

    def _request_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        发送单次 HTTP 请求获取向量
        """
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "input": texts}

        try:
            resp = requests.post(
                url, headers=headers, json=payload, timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()

        except Timeout as e:
            logger.error(f"Embedding request timed out: {url}")
            raise RuntimeError(f"Network Timeout: {e}") from e
        except RequestException as e:
            logger.error(f"Embedding network error: {e}")
            raise RuntimeError(f"Network Error: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse embedding response: {e}")
            raise RuntimeError(f"Response Parsing Error: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error during embedding: {e}")
            raise RuntimeError(f"System Error: {e}") from e

        items = data.get("data")
        if not isinstance(items, list) or len(items) != len(texts):
            raise RuntimeError(f"Unexpected API response format: {data}")

        vectors: List[List[float]] = []
        for item in items:
            emb = item.get("embedding")
            if not isinstance(emb, list):
                raise RuntimeError(f"Invalid embedding format in item: {item}")
            vectors.append([float(x) for x in emb])

        return vectors

    def embed_one(self, text: str) -> List[float]:
        """单条文本向量化"""
        vecs = self.embed_batch([text])
        if not vecs:
            raise RuntimeError("EmbeddingClient.embed_one: Empty result")
        return vecs[0]


# ===========================
# RAG 核心服务
# ===========================


class RAGService:
    """
    面向课程数据的 RAG 服务。
    支持上下文管理、并发安全。
    """

    def __init__(
        self,
        # [关键修改] 使用字符串做类型注解，避免运行时导入报错
        data_processor: "DataProcessor",
        *,
        persist_dir: str = "./chroma_store",
        embedding_client: Optional[EmbeddingClient] = None,
        auto_index: bool = True,
        top_k: int = 5,
    ) -> None:
        self.dp = data_processor
        self.embedder = embedding_client or EmbeddingClient()
        self.auto_index = auto_index
        self.default_top_k = top_k

        self._lock = threading.RLock()

        self.client = chromadb.PersistentClient(
            path=persist_dir, settings=Settings(allow_reset=False)
        )
        self._collections: Dict[str, chromadb.api.models.Collection.Collection] = {}

    def __enter__(self) -> "RAGService":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        pass

    # ---------- 内部：collection 获取 ---------- #

    def _get_collection(self, course_id: str):
        """获取或创建 collection，线程安全"""
        name = f"course_{course_id}"
        
        with self._lock:
            if name in self._collections:
                return self._collections[name]
            
            col = self.client.get_or_create_collection(name=name)
            self._collections[name] = col
            return col

    def _has_index(self, course_id: str) -> bool:
        try:
            col = self._get_collection(course_id)
            return col.count() > 0
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"Check index failed for {course_id}: {exc}")
            return False

    # ---------- 索引构建 ---------- #

    def ensure_index(self, course_id: str, *, reset: bool = False) -> bool:
        """
        确保指定课程已经建立向量索引。
        """
        course_id = str(course_id or "").strip()
        if not course_id:
            logger.warning("RAGService.ensure_index: Empty course_id")
            return False

        if not reset and self._has_index(course_id):
            return True

        with self._lock:
            if not reset and self._has_index(course_id):
                return True

            logger.info(f"Building index for course: {course_id}")
            
            course_data = self.dp.get_course_by_id(course_id)
            if not course_data:
                logger.warning(f"Course not found: {course_id}")
                return False

            try:
                corpus: List[CorpusItem] = self.dp.build_course_corpus(course_data)
            except Exception as exc:
                logger.exception(f"Build corpus failed: {exc}")
                return False

            if not corpus:
                logger.warning(f"Empty corpus for course: {course_id}")
                return False

            texts = [c.text for c in corpus]
            try:
                embeddings = self.embedder.embed_batch(texts)
            except Exception as exc:
                logger.exception(f"Vectorization failed: {exc}")
                return False

            if len(embeddings) != len(corpus):
                logger.error("Vector count mismatch")
                return False

            col = self._get_collection(course_id)
            if reset:
                try:
                    col_ids = col.get()['ids']
                    if col_ids:
                        col.delete(ids=col_ids)
                except Exception as exc:
                    logger.warning(f"Reset index warning: {exc}")

            ids = [f"{course_id}:{i}" for i in range(len(corpus))]
            documents = texts
            metadatas = [c.meta for c in corpus]

            col.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )

            logger.info(f"Indexed {len(corpus)} items for {course_id}")
            return True

    # ---------- 检索 ---------- #

    def retrieve(
        self,
        course_id: str,
        question: str,
        *,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        RAG 检索接口
        """
        course_id = str(course_id or "").strip()
        question = (question or "").strip()
        if not course_id or not question:
            return []

        if self.auto_index:
            if not self._has_index(course_id):
                ok = self.ensure_index(course_id)
                if not ok:
                    return []

        try:
            q_vec = self.embedder.embed_one(question)
        except Exception as exc:
            logger.exception(f"Query embedding failed: {exc}")
            return []

        col = self._get_collection(course_id)
        k = top_k or self.default_top_k

        try:
            result = col.query(query_embeddings=[q_vec], n_results=k)
        except Exception as exc:
            logger.exception(f"Chroma query failed: {exc}")
            return []

        docs = result.get("documents") or [[]]
        metas = result.get("metadatas") or [[]]
        dists = result.get("distances") or [[]]

        hits: List[Dict[str, Any]] = []
        if docs and len(docs) > 0:
            for text, meta, dist in zip(docs[0], metas[0], dists[0]):
                hits.append(
                    {
                        "text": text,
                        "meta": meta or {},
                        "score": float(dist),
                    }
                )
        return hits

    # ---------- 辅助工具 ---------- #

    @staticmethod
    def build_prompt_with_context(
        question: str, contexts: List[Dict[str, Any]]
    ) -> str:
        """构造 Prompt"""
        if not contexts:
            return question

        parts: List[str] = []
        for idx, item in enumerate(contexts, start=1):
            text = item.get("text", "")
            meta = item.get("meta", {})
            tag = meta.get("type", "info")
            week = meta.get("week")
            prefix = f"[{tag} | 第{week}周]" if week else f"[{tag}]"
            parts.append(f"片段{idx} {prefix}:\n{text}")

        ctx_block = "\n\n".join(parts)
        prompt = (
            "你是一名教学数据分析助手。下面是检索到的课程数据片段：\n"
            "====================\n"
            f"{ctx_block}\n"
            "====================\n"
            "请根据以上信息回答问题。若信息不足，请说明。\n\n"
            f"用户问题：{question}"
        )
        return prompt