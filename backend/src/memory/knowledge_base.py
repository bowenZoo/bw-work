"""
知识库管理

提供知识文档的导入、存储和检索功能。
P1: 仅支持 Markdown 格式
P2: 扩展支持 PDF 格式
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from src.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeDocument:
    """知识文档"""

    id: str
    title: str
    content: str
    source_path: str | None = None
    doc_type: str = "markdown"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class KnowledgeBase:
    """
    知识库管理

    管理知识文档的导入、存储和检索。
    结合向量搜索和关键词搜索提供知识检索功能。
    """

    def __init__(
        self,
        knowledge_dir: str = "data/knowledge",
        vector_store: VectorStore | None = None,
    ):
        """
        初始化知识库

        Args:
            knowledge_dir: 知识库目录
            vector_store: 向量存储实例（可选，不提供则自动创建）
        """
        self.knowledge_dir = Path(knowledge_dir)
        self.templates_dir = self.knowledge_dir / "templates"
        self.references_dir = self.knowledge_dir / "references"

        # 确保目录存在
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.references_dir.mkdir(parents=True, exist_ok=True)

        # 初始化向量存储
        if vector_store is None:
            chroma_dir = os.environ.get("CHROMA_PERSIST_DIR", "data/chroma")
            self._vector_store = VectorStore(
                persist_directory=chroma_dir,
                collection_name="knowledge",
            )
        else:
            self._vector_store = vector_store

        # 内存索引
        self._documents: dict[str, KnowledgeDocument] = {}

        # 加载已有文档
        self._load_existing_documents()

    def _load_existing_documents(self) -> None:
        """加载已有的知识文档"""
        for md_file in self.knowledge_dir.rglob("*.md"):
            if md_file.name.startswith("."):
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                title = self._extract_title(content, md_file.name)
                doc_id = str(uuid5(NAMESPACE_URL, str(md_file.resolve())))

                doc = KnowledgeDocument(
                    id=doc_id,
                    title=title,
                    content=content,
                    source_path=str(md_file),
                    doc_type="markdown",
                    metadata={
                        "source": str(md_file.relative_to(self.knowledge_dir)),
                        "doc_type": "markdown",
                    },
                )

                self._documents[doc_id] = doc
                self._vector_store.add(
                    text=content,
                    metadata={
                        "doc_id": doc_id,
                        "title": title,
                        "doc_type": "markdown",
                        "source": str(md_file.relative_to(self.knowledge_dir)),
                    },
                    doc_id=doc_id,
                )

            except Exception as e:
                logger.warning(f"Failed to load {md_file}: {e}")

    def _extract_title(self, content: str, fallback: str) -> str:
        """从内容中提取标题"""
        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return fallback

    def import_document(
        self,
        file_path: str,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocument | None:
        """
        导入文档

        Args:
            file_path: 文档文件路径
            metadata: 额外的元数据

        Returns:
            导入的文档对象，失败返回 None
        """
        path = Path(file_path)

        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        # 目前只支持 Markdown
        if path.suffix.lower() not in [".md", ".markdown"]:
            logger.warning(f"Unsupported file type: {path.suffix}. Only Markdown is supported in P1.")
            return None

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            return None

        # 创建文档
        doc_id = str(uuid4())
        title = self._extract_title(content, path.stem)

        doc_metadata = {
            "source": str(path.name),
            "type": "imported",
            "doc_type": "markdown",
        }
        if metadata:
            doc_metadata.update(metadata)

        doc = KnowledgeDocument(
            id=doc_id,
            title=title,
            content=content,
            source_path=str(path),
            doc_type="markdown",
            metadata=doc_metadata,
        )

        # 保存到内存索引
        self._documents[doc_id] = doc

        # 添加到向量存储
        self._vector_store.add(
            text=content,
            metadata={
                "doc_id": doc_id,
                "title": title,
                "doc_type": "markdown",
                **doc_metadata,
            },
            doc_id=doc_id,
        )

        logger.info(f"Imported document: {title} ({doc_id})")
        return doc

    def add_document(
        self,
        title: str,
        content: str,
        doc_type: str = "markdown",
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocument:
        """
        添加文档（不从文件导入）

        Args:
            title: 文档标题
            content: 文档内容
            doc_type: 文档类型
            metadata: 元数据

        Returns:
            创建的文档对象
        """
        doc_id = str(uuid4())

        doc = KnowledgeDocument(
            id=doc_id,
            title=title,
            content=content,
            doc_type=doc_type,
            metadata=metadata or {},
        )

        # 保存到内存索引
        self._documents[doc_id] = doc

        # 添加到向量存储
        self._vector_store.add(
            text=content,
            metadata={
                "doc_id": doc_id,
                "title": title,
                "doc_type": doc_type,
                **(metadata or {}),
            },
            doc_id=doc_id,
        )

        return doc

    def get_document(self, doc_id: str) -> KnowledgeDocument | None:
        """
        获取文档

        Args:
            doc_id: 文档 ID

        Returns:
            文档对象，不存在返回 None
        """
        return self._documents.get(doc_id)

    def search(
        self,
        query: str,
        limit: int = 10,
        doc_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        搜索知识库

        结合向量搜索和关键词匹配。

        Args:
            query: 搜索查询
            limit: 返回结果数量限制
            doc_type: 文档类型过滤

        Returns:
            搜索结果列表
        """
        # 准备过滤条件
        filter_metadata = None
        if doc_type:
            filter_metadata = {"doc_type": doc_type}

        # 向量搜索
        vector_results = self._vector_store.search(
            query=query,
            limit=limit,
            filter_metadata=filter_metadata,
        )

        # 合并结果
        results = []
        for vr in vector_results:
            doc_id = vr.get("metadata", {}).get("doc_id") or vr.get("id")
            doc = self._documents.get(doc_id)

            results.append({
                "id": doc_id,
                "title": vr.get("metadata", {}).get("title", "Unknown"),
                "content": vr.get("text", ""),
                "score": vr.get("score", 0),
                "document": doc,
            })

        return results

    def list_documents(
        self,
        doc_type: str | None = None,
        limit: int = 100,
    ) -> list[KnowledgeDocument]:
        """
        列出所有文档

        Args:
            doc_type: 文档类型过滤
            limit: 返回数量限制

        Returns:
            文档列表
        """
        docs = list(self._documents.values())

        if doc_type:
            docs = [d for d in docs if d.doc_type == doc_type]

        # 按更新时间倒序
        docs.sort(key=lambda d: d.updated_at, reverse=True)

        return docs[:limit]

    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档

        Args:
            doc_id: 文档 ID

        Returns:
            是否成功删除
        """
        if doc_id not in self._documents:
            return False

        # 从内存索引删除
        del self._documents[doc_id]

        # 从向量存储删除
        self._vector_store.delete(doc_id)

        return True

    # === 模板管理 ===

    def list_templates(self) -> list[KnowledgeDocument]:
        """
        列出所有模板

        Returns:
            模板文档列表
        """
        templates = []

        for md_file in self.templates_dir.glob("*.md"):
            if md_file.name.startswith("."):
                continue

            try:
                content = md_file.read_text(encoding="utf-8")
                title = self._extract_title(content, md_file.stem)

                templates.append(
                    KnowledgeDocument(
                        id=md_file.stem,
                        title=title,
                        content=content,
                        source_path=str(md_file),
                        doc_type="template",
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to load template {md_file}: {e}")

        return templates

    def get_template(self, template_name: str) -> KnowledgeDocument | None:
        """
        获取模板

        Args:
            template_name: 模板名称（不含扩展名）

        Returns:
            模板文档，不存在返回 None
        """
        template_path = self.templates_dir / f"{template_name}.md"

        if not template_path.exists():
            return None

        try:
            content = template_path.read_text(encoding="utf-8")
            title = self._extract_title(content, template_name)

            return KnowledgeDocument(
                id=template_name,
                title=title,
                content=content,
                source_path=str(template_path),
                doc_type="template",
            )
        except Exception as e:
            logger.error(f"Failed to load template: {e}")
            return None

    def save_template(self, name: str, content: str) -> bool:
        """
        保存模板

        Args:
            name: 模板名称
            content: 模板内容

        Returns:
            是否成功保存
        """
        template_path = self.templates_dir / f"{name}.md"

        try:
            template_path.write_text(content, encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"Failed to save template: {e}")
            return False

    def __repr__(self) -> str:
        """字符串表示"""
        return f"KnowledgeBase(documents={len(self._documents)}, dir='{self.knowledge_dir}')"
