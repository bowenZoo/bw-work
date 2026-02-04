"""
向量存储单元测试
"""

import os
import shutil
import tempfile

import pytest

from src.memory.vector_store import VectorStore


@pytest.fixture
def temp_persist_dir():
    """创建临时持久化目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def vector_store(temp_persist_dir):
    """创建 VectorStore 实例"""
    return VectorStore(persist_directory=temp_persist_dir, collection_name="test")


class TestVectorStore:
    """VectorStore 测试"""

    def test_init(self, temp_persist_dir):
        """测试初始化"""
        vs = VectorStore(persist_directory=temp_persist_dir)
        assert vs.persist_directory.exists()

    def test_repr(self, vector_store):
        """测试字符串表示"""
        repr_str = repr(vector_store)
        assert "VectorStore" in repr_str
        assert "test" in repr_str

    def test_add_and_search(self, vector_store):
        """测试添加和搜索"""
        # 添加文档
        doc_id = vector_store.add(
            text="战斗系统需要实现回合制机制",
            metadata={"type": "design"},
        )
        assert doc_id is not None

        # 搜索
        results = vector_store.search("战斗")
        assert len(results) >= 1
        assert results[0]["text"] == "战斗系统需要实现回合制机制"

    def test_add_multiple_and_search(self, vector_store):
        """测试添加多个文档并搜索"""
        # 添加多个文档
        vector_store.add(text="战斗系统设计文档", metadata={"type": "combat"})
        vector_store.add(text="经济系统设计文档", metadata={"type": "economy"})
        vector_store.add(text="战斗数值平衡", metadata={"type": "combat"})

        # 搜索
        results = vector_store.search("战斗", limit=10)
        assert len(results) >= 2

    def test_search_with_limit(self, vector_store):
        """测试搜索限制"""
        # 添加多个文档
        for i in range(5):
            vector_store.add(text=f"测试文档 {i}", metadata={"index": i})

        # 限制返回数量
        results = vector_store.search("测试", limit=2)
        assert len(results) <= 2

    def test_delete(self, vector_store):
        """测试删除"""
        # 添加文档
        doc_id = vector_store.add(text="要删除的文档")
        assert vector_store.count() >= 1

        # 删除
        result = vector_store.delete(doc_id)
        assert result is True

    def test_update(self, vector_store):
        """测试更新"""
        # 添加文档
        doc_id = vector_store.add(text="原始内容")

        # 更新
        result = vector_store.update(doc_id, text="更新后的内容")
        assert result is True

        # 验证更新
        results = vector_store.search("更新后")
        assert len(results) >= 1

    def test_count(self, vector_store):
        """测试计数"""
        initial_count = vector_store.count()

        vector_store.add(text="新文档")
        assert vector_store.count() == initial_count + 1

    def test_clear(self, vector_store):
        """测试清空"""
        # 添加文档
        vector_store.add(text="文档1")
        vector_store.add(text="文档2")
        assert vector_store.count() >= 2

        # 清空
        result = vector_store.clear()
        assert result is True
        assert vector_store.count() == 0

    def test_disabled_mode(self, temp_persist_dir):
        """测试禁用模式"""
        vs = VectorStore(persist_directory=temp_persist_dir, enabled=False)
        assert not vs.is_vector_enabled

        # 仍然可以添加（只是不会向量化）
        doc_id = vs.add(text="测试文档")
        assert doc_id is not None

    def test_search_empty_results(self, vector_store):
        """测试搜索空结果"""
        results = vector_store.search("不存在的内容xyz123")
        assert len(results) == 0

    def test_metadata_filter(self, vector_store):
        """测试元数据过滤"""
        # 添加带不同类型的文档
        vector_store.add(text="战斗设计1", metadata={"type": "combat"})
        vector_store.add(text="经济设计1", metadata={"type": "economy"})
        vector_store.add(text="战斗设计2", metadata={"type": "combat"})

        # 按类型过滤
        results = vector_store.search("设计", filter_metadata={"type": "combat"})
        assert all(r["metadata"].get("type") == "combat" for r in results)

    def test_env_var_config(self, temp_persist_dir):
        """测试环境变量配置"""
        # 设置环境变量
        os.environ["CHROMA_PERSIST_DIR"] = temp_persist_dir
        os.environ["VECTOR_STORE_ENABLED"] = "true"

        try:
            vs = VectorStore()
            assert str(vs.persist_directory) == temp_persist_dir
        finally:
            # 清理环境变量
            del os.environ["CHROMA_PERSIST_DIR"]
            del os.environ["VECTOR_STORE_ENABLED"]
