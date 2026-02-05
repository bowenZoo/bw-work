"""
向量存储

使用 Chroma 向量数据库实现语义搜索。
支持降级模式：当 embedding 模型不可用时，回退到关键词搜索。
"""

import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class VectorStore:
    """
    向量存储

    使用 Chroma 进行向量化存储和语义搜索。
    支持降级模式，当向量化不可用时回退到关键词搜索。
    """

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str = "default",
        enabled: bool | None = None,
    ):
        """
        初始化向量存储

        Args:
            persist_directory: 持久化目录，默认从环境变量读取
            collection_name: 集合名称
            enabled: 是否启用向量存储，默认从环境变量读取
        """
        # 从环境变量读取配置
        if persist_directory is None:
            persist_directory = os.environ.get("CHROMA_PERSIST_DIR", "data/chroma")

        if enabled is None:
            enabled = os.environ.get("VECTOR_STORE_ENABLED", "true").lower() == "true"

        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self._enabled = enabled
        self._client = None
        self._collection = None
        self._fallback_mode = False
        self._fallback_docs: dict[str, dict[str, Any]] = {}

        if self._enabled:
            self._init_chroma()

    def _init_chroma(self) -> None:
        """初始化 Chroma 客户端"""
        try:
            import chromadb
            from chromadb.config import Settings

            # 确保目录存在
            self.persist_directory.mkdir(parents=True, exist_ok=True)

            # 创建持久化客户端
            self._client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(anonymized_telemetry=False),
            )

            # 获取或创建集合
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

            logger.info(f"Chroma initialized: {self.persist_directory}")

        except ImportError as e:
            logger.warning(f"Chroma not available: {e}. Falling back to keyword search.")
            self._fallback_mode = True
        except Exception as e:
            logger.warning(f"Chroma initialization failed: {e}. Falling back to keyword search.")
            self._fallback_mode = True

    @property
    def is_vector_enabled(self) -> bool:
        """是否启用向量搜索"""
        return self._enabled and not self._fallback_mode and self._collection is not None

    def _store_fallback_doc(self, doc_id: str, text: str, metadata: dict[str, Any]) -> None:
        """Store a document in the fallback index for keyword search."""
        self._fallback_docs[doc_id] = {
            "text": text,
            "metadata": metadata,
        }

    def _metadata_matches(self, metadata: dict[str, Any], filter_metadata: dict[str, Any]) -> bool:
        """Check if metadata matches the filter criteria."""
        for key, value in filter_metadata.items():
            if metadata.get(key) != value:
                return False
        return True

    def add(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        doc_id: str | None = None,
    ) -> str:
        """
        添加文本到向量存储

        Args:
            text: 文本内容
            metadata: 元数据
            doc_id: 文档 ID，如果不指定则自动生成

        Returns:
            文档 ID
        """
        if doc_id is None:
            doc_id = str(uuid4())

        if metadata is None:
            metadata = {}
        else:
            metadata = dict(metadata)

        # 存储原始文本用于降级模式
        metadata["_text"] = text
        self._store_fallback_doc(doc_id, text, metadata)

        if self.is_vector_enabled:
            try:
                if hasattr(self._collection, "upsert"):
                    self._collection.upsert(
                        documents=[text],
                        metadatas=[metadata],
                        ids=[doc_id],
                    )
                else:
                    self._collection.add(
                        documents=[text],
                        metadatas=[metadata],
                        ids=[doc_id],
                    )
            except Exception as e:
                logger.warning(f"Failed to add to vector store: {e}")

        return doc_id

    def search(
        self,
        query: str,
        limit: int = 10,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        搜索相似文本

        Args:
            query: 查询文本
            limit: 返回结果数量限制
            filter_metadata: 元数据过滤条件

        Returns:
            搜索结果列表，每个结果包含 id, text, metadata, score
        """
        if self.is_vector_enabled:
            return self._vector_search(query, limit, filter_metadata)
        else:
            return self._keyword_search(query, limit, filter_metadata)

    def _vector_search(
        self,
        query: str,
        limit: int,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """向量语义搜索"""
        try:
            where = filter_metadata if filter_metadata else None

            results = self._collection.query(
                query_texts=[query],
                n_results=limit,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

            output = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    output.append({
                        "id": doc_id,
                        "text": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "score": 1 - results["distances"][0][i] if results["distances"] else 0,
                    })

            return output

        except Exception as e:
            logger.warning(f"Vector search failed: {e}. Falling back to keyword search.")
            self._fallback_mode = True
            return self._keyword_search(query, limit, filter_metadata)

    def _keyword_search(
        self,
        query: str,
        limit: int,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """关键词搜索（降级模式）"""
        # Prefer in-memory fallback index when available
        if self._fallback_docs:
            try:
                query_terms = set(query.lower().split())
                results = []

                for doc_id, doc in self._fallback_docs.items():
                    metadata = doc.get("metadata", {})
                    if filter_metadata and not self._metadata_matches(metadata, filter_metadata):
                        continue

                    text = doc.get("text", "")
                    text_lower = text.lower()
                    matches = sum(1 for term in query_terms if term in text_lower)

                    if matches > 0:
                        score = matches / len(query_terms)
                        results.append(
                            {
                                "id": doc_id,
                                "text": text,
                                "metadata": metadata,
                                "score": score,
                            }
                        )

                results.sort(key=lambda x: x["score"], reverse=True)
                return results[:limit]
            except Exception as e:
                logger.error(f"Keyword search failed: {e}")
                return []

        if not self._collection:
            return []

        try:
            # 获取所有文档
            all_docs = self._collection.get(
                include=["documents", "metadatas"],
                where=filter_metadata if filter_metadata else None,
            )

            if not all_docs["ids"]:
                return []

            # 简单的关键词匹配和评分
            query_terms = set(query.lower().split())
            results = []

            for i, doc_id in enumerate(all_docs["ids"]):
                text = all_docs["documents"][i] if all_docs["documents"] else ""
                metadata = all_docs["metadatas"][i] if all_docs["metadatas"] else {}

                # 计算匹配分数
                text_lower = text.lower()
                matches = sum(1 for term in query_terms if term in text_lower)

                if matches > 0:
                    score = matches / len(query_terms)
                    results.append({
                        "id": doc_id,
                        "text": text,
                        "metadata": metadata,
                        "score": score,
                    })

            # 按分数排序
            results.sort(key=lambda x: x["score"], reverse=True)

            return results[:limit]

        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []

    def delete(self, doc_id: str) -> bool:
        """
        删除文档

        Args:
            doc_id: 文档 ID

        Returns:
            是否成功删除
        """
        removed = self._fallback_docs.pop(doc_id, None) is not None

        if not self._collection:
            return removed

        try:
            self._collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return removed

    def update(
        self,
        doc_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        更新文档

        Args:
            doc_id: 文档 ID
            text: 新的文本内容
            metadata: 新的元数据

        Returns:
            是否成功更新
        """
        if metadata is None:
            metadata = {}
        else:
            metadata = dict(metadata)

        metadata["_text"] = text
        self._store_fallback_doc(doc_id, text, metadata)

        if not self._collection:
            return True

        try:
            self._collection.update(
                ids=[doc_id],
                documents=[text],
                metadatas=[metadata],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update document: {e}")
            return True

    def count(self) -> int:
        """获取文档数量"""
        if not self._collection:
            return len(self._fallback_docs)

        try:
            return self._collection.count()
        except Exception:
            return 0

    def clear(self) -> bool:
        """清空集合"""
        if not self._client:
            self._fallback_docs.clear()
            return True

        try:
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self._fallback_docs.clear()
            return True
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            return False

    def __repr__(self) -> str:
        """字符串表示"""
        mode = "vector" if self.is_vector_enabled else "keyword (fallback)"
        return f"VectorStore(collection='{self.collection_name}', mode='{mode}')"
