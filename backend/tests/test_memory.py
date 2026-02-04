"""
记忆系统单元测试
"""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from src.memory.base import Discussion, Message
from src.memory.discussion_memory import DiscussionMemory


@pytest.fixture
def temp_data_dir():
    """创建临时数据目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def discussion_memory(temp_data_dir):
    """创建 DiscussionMemory 实例"""
    return DiscussionMemory(data_dir=temp_data_dir, archive_threshold=5)


@pytest.fixture
def sample_discussion():
    """创建示例讨论"""
    return Discussion(
        id=str(uuid4()),
        project_id="test-project",
        topic="战斗系统设计讨论",
        messages=[
            Message(
                id=str(uuid4()),
                agent_id="system_designer",
                agent_role="系统策划",
                content="我们需要讨论战斗系统的核心机制",
                timestamp=datetime.now(),
            ),
            Message(
                id=str(uuid4()),
                agent_id="number_designer",
                agent_role="数值策划",
                content="从数值角度，我建议采用等级 * 基础值的公式",
                timestamp=datetime.now(),
            ),
        ],
        summary="讨论了战斗系统的基本框架",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


class TestDiscussionMemory:
    """DiscussionMemory 测试"""

    def test_init(self, temp_data_dir):
        """测试初始化"""
        dm = DiscussionMemory(data_dir=temp_data_dir)
        assert dm.data_dir == Path(temp_data_dir)
        assert dm.archive_threshold == 100

    def test_repr(self, discussion_memory):
        """测试字符串表示"""
        repr_str = repr(discussion_memory)
        assert "DiscussionMemory" in repr_str
        assert "archive_threshold=5" in repr_str

    def test_save_and_load(self, discussion_memory, sample_discussion):
        """测试保存和加载"""
        # 保存
        discussion_id = discussion_memory.save(sample_discussion)
        assert discussion_id == sample_discussion.id

        # 加载
        loaded = discussion_memory.load(discussion_id)
        assert loaded is not None
        assert loaded.id == sample_discussion.id
        assert loaded.topic == sample_discussion.topic
        assert loaded.project_id == sample_discussion.project_id
        assert len(loaded.messages) == len(sample_discussion.messages)

    def test_load_nonexistent(self, discussion_memory):
        """测试加载不存在的讨论"""
        result = discussion_memory.load("nonexistent-id")
        assert result is None

    def test_delete(self, discussion_memory, sample_discussion):
        """测试删除"""
        # 保存
        discussion_id = discussion_memory.save(sample_discussion)

        # 验证存在
        assert discussion_memory.load(discussion_id) is not None

        # 删除
        result = discussion_memory.delete(discussion_id)
        assert result is True

        # 验证已删除
        assert discussion_memory.load(discussion_id) is None

    def test_delete_nonexistent(self, discussion_memory):
        """测试删除不存在的讨论"""
        result = discussion_memory.delete("nonexistent-id")
        assert result is False

    def test_list_all(self, discussion_memory):
        """测试列出所有讨论"""
        # 创建多个讨论
        for i in range(3):
            discussion = Discussion(
                id=str(uuid4()),
                project_id="test-project",
                topic=f"讨论 {i}",
                messages=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            discussion_memory.save(discussion)

        # 列出所有
        all_discussions = discussion_memory.list_all()
        assert len(all_discussions) == 3

    def test_list_by_project(self, discussion_memory):
        """测试按项目列出讨论"""
        # 创建不同项目的讨论
        for project_id in ["project-a", "project-a", "project-b"]:
            discussion = Discussion(
                id=str(uuid4()),
                project_id=project_id,
                topic=f"{project_id} 讨论",
                messages=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            discussion_memory.save(discussion)

        # 按项目列出
        project_a_discussions = discussion_memory.list_by_project("project-a")
        assert len(project_a_discussions) == 2

        project_b_discussions = discussion_memory.list_by_project("project-b")
        assert len(project_b_discussions) == 1

    def test_search(self, discussion_memory):
        """测试搜索"""
        # 创建讨论
        topics = ["战斗系统设计", "经济系统规划", "战斗数值平衡"]
        for topic in topics:
            discussion = Discussion(
                id=str(uuid4()),
                project_id="test-project",
                topic=topic,
                messages=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            discussion_memory.save(discussion)

        # 搜索
        results = discussion_memory.search("战斗")
        assert len(results) == 2

        results = discussion_memory.search("经济")
        assert len(results) == 1

    def test_add_message(self, discussion_memory, sample_discussion):
        """测试添加消息"""
        # 保存讨论
        discussion_id = discussion_memory.save(sample_discussion)
        original_count = len(sample_discussion.messages)

        # 添加消息
        new_message = Message(
            id=str(uuid4()),
            agent_id="player_advocate",
            agent_role="玩家代言人",
            content="作为玩家，我觉得这个设计很有趣",
            timestamp=datetime.now(),
        )
        result = discussion_memory.add_message(discussion_id, new_message)
        assert result is True

        # 验证消息已添加
        loaded = discussion_memory.load(discussion_id)
        assert len(loaded.messages) == original_count + 1

    def test_add_message_to_nonexistent(self, discussion_memory):
        """测试向不存在的讨论添加消息"""
        message = Message(
            id=str(uuid4()),
            agent_id="test",
            agent_role="测试",
            content="测试消息",
            timestamp=datetime.now(),
        )
        result = discussion_memory.add_message("nonexistent-id", message)
        assert result is False

    def test_auto_archive(self, discussion_memory):
        """测试自动归档"""
        # 创建超过阈值的讨论（阈值为 5）
        discussion_ids = []
        for i in range(7):
            discussion = Discussion(
                id=str(uuid4()),
                project_id="archive-test",
                topic=f"讨论 {i}",
                messages=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            discussion_ids.append(discussion_memory.save(discussion))

        # 验证活跃讨论数量为阈值
        active_discussions = discussion_memory.list_by_project("archive-test")
        assert len(active_discussions) == 5

        # 验证归档目录存在文件
        archive_dir = discussion_memory.data_dir / "archive-test" / "archive"
        assert archive_dir.exists()
        archived_files = list(archive_dir.glob("*.json"))
        assert len(archived_files) == 2

    def test_pagination(self, temp_data_dir):
        """测试分页"""
        # 使用较大的归档阈值，避免归档影响测试
        dm = DiscussionMemory(data_dir=temp_data_dir, archive_threshold=100)

        # 创建多个讨论
        for i in range(10):
            discussion = Discussion(
                id=str(uuid4()),
                project_id="test-project",
                topic=f"讨论 {i}",
                messages=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            dm.save(discussion)

        # 测试分页
        page1 = dm.list_all(offset=0, limit=3)
        assert len(page1) == 3

        page2 = dm.list_all(offset=3, limit=3)
        assert len(page2) == 3

        # 验证不重复
        page1_ids = {d.id for d in page1}
        page2_ids = {d.id for d in page2}
        assert page1_ids.isdisjoint(page2_ids)
