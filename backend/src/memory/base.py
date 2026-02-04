"""
记忆系统接口定义

定义 MemoryStore 抽象基类，所有记忆存储实现需继承此类。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class Message:
    """消息模型"""

    id: str
    agent_id: str
    agent_role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Discussion:
    """讨论模型"""

    id: str
    project_id: str
    topic: str
    messages: list[Message] = field(default_factory=list)
    summary: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Decision:
    """决策模型"""

    id: str
    discussion_id: str
    title: str
    description: str
    rationale: str
    made_by: str
    created_at: datetime = field(default_factory=datetime.now)


class MemoryStore(ABC, Generic[T]):
    """
    记忆存储抽象基类

    所有记忆存储实现（讨论记忆、决策追踪、向量存储等）需继承此类。
    """

    @abstractmethod
    def save(self, item: T) -> str:
        """
        保存记录

        Args:
            item: 要保存的记录

        Returns:
            记录 ID
        """
        pass

    @abstractmethod
    def load(self, item_id: str) -> Optional[T]:
        """
        加载记录

        Args:
            item_id: 记录 ID

        Returns:
            记录对象，不存在时返回 None
        """
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[T]:
        """
        搜索记录

        Args:
            query: 搜索查询
            limit: 返回结果数量限制

        Returns:
            匹配的记录列表
        """
        pass

    @abstractmethod
    def delete(self, item_id: str) -> bool:
        """
        删除记录

        Args:
            item_id: 记录 ID

        Returns:
            是否成功删除
        """
        pass

    @abstractmethod
    def list_all(self, offset: int = 0, limit: int = 100) -> list[T]:
        """
        列出所有记录

        Args:
            offset: 起始位置
            limit: 返回数量限制

        Returns:
            记录列表
        """
        pass
