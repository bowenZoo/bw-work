"""
讨论记忆存储

实现讨论保存和加载：
- JSON 文件：讨论正文（事实来源）
- SQLite：索引和元数据（用于快速查询）
- 自动归档：超过阈值的旧讨论移至 archive/
"""

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from src.memory.base import Discussion, MemoryStore, Message


class DiscussionMemory(MemoryStore[Discussion]):
    """
    讨论记忆存储

    使用 JSON 文件作为事实来源，SQLite 作为索引。
    """

    def __init__(
        self,
        data_dir: str = "data/projects",
        archive_threshold: int = 100,
    ):
        """
        初始化讨论记忆

        Args:
            data_dir: 数据目录路径
            archive_threshold: 自动归档阈值（超过此数量的讨论将被归档）
        """
        self.data_dir = Path(data_dir)
        self.archive_threshold = archive_threshold
        self._db_path = self.data_dir / ".index.db"

        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 SQLite 索引
        self._init_db()

    def _init_db(self) -> None:
        """初始化 SQLite 索引数据库"""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS discussions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                summary TEXT,
                message_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived INTEGER DEFAULT 0,
                file_path TEXT NOT NULL
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_project_id ON discussions(project_id)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_created_at ON discussions(created_at)
        """
        )

        # Add content_text column for message search if missing
        cursor.execute("PRAGMA table_info(discussions)")
        columns = {row[1] for row in cursor.fetchall()}
        if "content_text" not in columns:
            cursor.execute("ALTER TABLE discussions ADD COLUMN content_text TEXT")

        conn.commit()
        conn.close()

    def _connect(self) -> sqlite3.Connection:
        """Create a SQLite connection with safer concurrency defaults."""
        conn = sqlite3.connect(self._db_path, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _build_content_text(self, discussion: Discussion) -> str:
        parts = [discussion.topic or ""]
        if discussion.summary:
            parts.append(discussion.summary)
        parts.extend([msg.content for msg in discussion.messages if msg.content])
        return "\n".join(p for p in parts if p)

    def _update_content_text(self, discussion: Discussion) -> None:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE discussions SET content_text = ? WHERE id = ?",
            (self._build_content_text(discussion), discussion.id),
        )
        conn.commit()
        conn.close()

    def _get_discussion_path(
        self, project_id: str, discussion_id: str, archived: bool = False
    ) -> Path:
        """获取讨论文件路径"""
        subdir = "archive" if archived else "discussions"
        return self.data_dir / project_id / subdir / f"{discussion_id}.json"

    def _discussion_to_dict(self, discussion: Discussion) -> dict:
        """将 Discussion 对象转换为字典"""
        return {
            "id": discussion.id,
            "project_id": discussion.project_id,
            "topic": discussion.topic,
            "messages": [
                {
                    "id": msg.id,
                    "agent_id": msg.agent_id,
                    "agent_role": msg.agent_role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in discussion.messages
            ],
            "summary": discussion.summary,
            "created_at": discussion.created_at.isoformat(),
            "updated_at": discussion.updated_at.isoformat(),
        }

    def _dict_to_discussion(self, data: dict) -> Discussion:
        """将字典转换为 Discussion 对象"""
        return Discussion(
            id=data["id"],
            project_id=data["project_id"],
            topic=data["topic"],
            messages=[
                Message(
                    id=msg["id"],
                    agent_id=msg["agent_id"],
                    agent_role=msg["agent_role"],
                    content=msg["content"],
                    timestamp=datetime.fromisoformat(msg["timestamp"]),
                )
                for msg in data.get("messages", [])
            ],
            summary=data.get("summary"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    def save(self, discussion: Discussion) -> str:
        """
        保存讨论

        Args:
            discussion: 讨论对象

        Returns:
            讨论 ID
        """
        # 确保有 ID
        if not discussion.id:
            discussion.id = str(uuid4())

        # 更新时间戳
        discussion.updated_at = datetime.now()

        # 保存 JSON 文件
        file_path = self._get_discussion_path(discussion.project_id, discussion.id)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file then rename to prevent corruption
        fd, tmp_path = tempfile.mkstemp(dir=str(file_path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._discussion_to_dict(discussion), f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(file_path))
        except BaseException:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # 更新 SQLite 索引
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO discussions
            (
                id,
                project_id,
                topic,
                summary,
                message_count,
                created_at,
                updated_at,
                archived,
                file_path,
                content_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                discussion.id,
                discussion.project_id,
                discussion.topic,
                discussion.summary,
                len(discussion.messages),
                discussion.created_at.isoformat(),
                discussion.updated_at.isoformat(),
                0,
                str(file_path),
                self._build_content_text(discussion),
            ),
        )

        conn.commit()
        conn.close()

        # 检查是否需要归档
        self._check_and_archive(discussion.project_id)

        return discussion.id

    def load(self, discussion_id: str) -> Discussion | None:
        """
        加载讨论

        Args:
            discussion_id: 讨论 ID

        Returns:
            讨论对象，不存在时返回 None
        """
        # 先从索引查找文件路径
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT file_path, archived FROM discussions WHERE id = ?",
            (discussion_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        file_path = Path(row[0])

        if not file_path.exists():
            return None

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        discussion = self._dict_to_discussion(data)
        self._update_content_text(discussion)
        return discussion

    def search(self, query: str, limit: int = 10) -> list[Discussion]:
        """
        搜索讨论

        按主题或摘要进行关键词搜索。

        Args:
            query: 搜索关键词
            limit: 返回结果数量限制

        Returns:
            匹配的讨论列表
        """
        query_lower = query.lower()
        conn = self._connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT id FROM discussions
                WHERE (topic LIKE ? OR summary LIKE ? OR content_text LIKE ?)
                AND archived = 0
                ORDER BY updated_at DESC
                LIMIT ?
            """,
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            )

            rows = cursor.fetchall()

            results = []
            seen_ids: set[str] = set()
            for row in rows:
                discussion = self.load(row[0])
                if discussion:
                    results.append(discussion)
                    seen_ids.add(discussion.id)
                    if len(results) >= limit:
                        return results

            # If not enough results, scan message content for matches (fallback)
            if len(results) < limit:
                scan_limit = max(limit * 5, 50)
                cursor.execute(
                    """
                    SELECT id FROM discussions
                    WHERE archived = 0
                    ORDER BY updated_at DESC
                    LIMIT ?
                """
                ,
                    (scan_limit,),
                )
                all_rows = cursor.fetchall()

                for row in all_rows:
                    if len(results) >= limit:
                        break
                    discussion_id = row[0]
                    if discussion_id in seen_ids:
                        continue
                    discussion = self.load(discussion_id)
                    if not discussion:
                        continue
                    for message in discussion.messages:
                        if query_lower in message.content.lower():
                            results.append(discussion)
                            seen_ids.add(discussion_id)
                            break

                return results

            return results
        finally:
            conn.close()

    def delete(self, discussion_id: str) -> bool:
        """
        删除讨论

        Args:
            discussion_id: 讨论 ID

        Returns:
            是否成功删除
        """
        # 获取文件路径
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT file_path FROM discussions WHERE id = ?",
            (discussion_id,),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False

        file_path = Path(row[0])

        # 删除文件
        if file_path.exists():
            file_path.unlink()

        # 删除索引
        cursor.execute("DELETE FROM discussions WHERE id = ?", (discussion_id,))
        conn.commit()
        conn.close()

        return True

    def list_all(self, offset: int = 0, limit: int = 100) -> list[Discussion]:
        """
        列出所有讨论

        Args:
            offset: 起始位置
            limit: 返回数量限制

        Returns:
            讨论列表
        """
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id FROM discussions
            WHERE archived = 0
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """,
            (limit, offset),
        )

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            discussion = self.load(row[0])
            if discussion:
                results.append(discussion)

        return results

    def list_by_project(
        self, project_id: str, offset: int = 0, limit: int = 100
    ) -> list[Discussion]:
        """
        列出项目的所有讨论

        Args:
            project_id: 项目 ID
            offset: 起始位置
            limit: 返回数量限制

        Returns:
            讨论列表
        """
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id FROM discussions
            WHERE project_id = ? AND archived = 0
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """,
            (project_id, limit, offset),
        )

        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            discussion = self.load(row[0])
            if discussion:
                results.append(discussion)

        return results

    def add_message(self, discussion_id: str, message: Message) -> bool:
        """
        向讨论添加消息

        Args:
            discussion_id: 讨论 ID
            message: 消息对象

        Returns:
            是否成功添加
        """
        discussion = self.load(discussion_id)
        if not discussion:
            return False

        discussion.messages.append(message)
        self.save(discussion)
        return True

    def _check_and_archive(self, project_id: str) -> None:
        """
        检查并执行自动归档

        当项目讨论数量超过阈值时，将旧讨论移至 archive/
        """
        conn = self._connect()
        cursor = conn.cursor()

        # 获取项目讨论数量
        cursor.execute(
            "SELECT COUNT(*) FROM discussions WHERE project_id = ? AND archived = 0",
            (project_id,),
        )
        count = cursor.fetchone()[0]

        if count <= self.archive_threshold:
            conn.close()
            return

        # 获取需要归档的讨论（按时间排序，保留最新的 threshold 条）
        to_archive_count = count - self.archive_threshold
        cursor.execute(
            """
            SELECT id, file_path FROM discussions
            WHERE project_id = ? AND archived = 0
            ORDER BY updated_at ASC
            LIMIT ?
        """,
            (project_id, to_archive_count),
        )

        rows = cursor.fetchall()

        for row in rows:
            discussion_id, old_path = row
            old_path = Path(old_path)

            # 创建归档目录
            archive_path = self._get_discussion_path(project_id, discussion_id, archived=True)
            archive_path.parent.mkdir(parents=True, exist_ok=True)

            # 移动文件
            if old_path.exists():
                shutil.move(str(old_path), str(archive_path))

            # 更新索引
            cursor.execute(
                "UPDATE discussions SET archived = 1, file_path = ? WHERE id = ?",
                (str(archive_path), discussion_id),
            )

        conn.commit()
        conn.close()

    def __repr__(self) -> str:
        """字符串表示"""
        return f"DiscussionMemory(data_dir='{self.data_dir}', archive_threshold={self.archive_threshold})"
