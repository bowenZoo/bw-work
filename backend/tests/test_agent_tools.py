"""Tests for crew agent tools (calculator, table, industry data, memory search, doc reader, vote)."""

import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend/src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Disable CrewAI telemetry before any crewai imports
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_TESTING", "true")

from src.crew.tools import (
    get_calculator_tool,
    get_industry_data_tool,
    get_table_tool,
    create_memory_search_tool,
    create_read_project_doc_tool,
    create_request_vote_tool,
)


# ===================================================================
# Calculator Tool Tests
# ===================================================================

class TestCalculatorTool:
    """Tests for the safe math calculator tool."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.calc = get_calculator_tool()

    def test_basic_arithmetic(self):
        assert self.calc.run("2 + 3") == "5"
        assert self.calc.run("10 - 4") == "6"
        assert self.calc.run("6 * 7") == "42"
        assert self.calc.run("15 / 4") == "3.75"

    def test_power_and_growth(self):
        result = float(self.calc.run("1.5 ** 10"))
        assert abs(result - 57.6650390625) < 0.001

    def test_math_functions(self):
        assert self.calc.run("math.sqrt(144)") == "12.0"
        assert self.calc.run("math.log2(1024)") == "10.0"
        result = float(self.calc.run("math.pi"))
        assert abs(result - 3.14159) < 0.001

    def test_builtins(self):
        assert self.calc.run("abs(-5)") == "5"
        assert self.calc.run("max(3, 7, 1)") == "7"
        assert self.calc.run("round(3.14159, 2)") == "3.14"

    def test_complex_expression(self):
        # Revenue estimate: DAU * pay_rate * ARPPU
        result = float(self.calc.run("100000 * 0.03 * 50"))
        assert result == 150000.0

    def test_division_by_zero(self):
        result = self.calc.run("1 / 0")
        assert "除以零" in result

    def test_empty_expression(self):
        result = self.calc.run("")
        assert "错误" in result

    def test_too_long_expression(self):
        result = self.calc.run("1 + " * 200)
        assert "过长" in result

    def test_reject_import(self):
        result = self.calc.run("__import__('os')")
        assert "不允许" in result or "错误" in result

    def test_reject_exec(self):
        result = self.calc.run("exec('print(1)')")
        assert "不允许" in result or "错误" in result

    def test_reject_open(self):
        result = self.calc.run("open('/etc/passwd')")
        assert "不允许" in result or "错误" in result

    def test_reject_dunder(self):
        result = self.calc.run("().__class__.__bases__")
        assert "不允许" in result or "错误" in result

    def test_syntax_error(self):
        result = self.calc.run("2 +* 3")
        assert "语法错误" in result or "错误" in result or "计算错误" in result


# ===================================================================
# Table Tool Tests
# ===================================================================

class TestTableTool:
    """Tests for the markdown table generator tool."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.table = get_table_tool()

    def test_basic_table(self):
        result = self.table.run(headers="名称,值", rows="A,1;B,2")
        assert "| 名称 | 值 |" in result
        assert "| A | 1 |" in result
        assert "| B | 2 |" in result
        assert "---" in result

    def test_headers_only(self):
        result = self.table.run(headers="列1,列2,列3", rows="")
        assert "| 列1 | 列2 | 列3 |" in result
        assert "---" in result

    def test_mismatched_columns(self):
        """Rows with fewer cols should be padded."""
        result = self.table.run(headers="A,B,C", rows="1,2")
        assert "| 1 | 2 |  |" in result

    def test_empty_headers(self):
        result = self.table.run(headers="", rows="a,b")
        assert "错误" in result

    def test_comparison_table(self):
        result = self.table.run(
            headers="方案,优势,劣势",
            rows="方案A,低成本,功能少;方案B,功能全,成本高"
        )
        assert "方案A" in result
        assert "方案B" in result


# ===================================================================
# Game Industry Data Tool Tests
# ===================================================================

class TestIndustryDataTool:
    """Tests for the game industry data lookup tool."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.industry = get_industry_data_tool()

    def test_payment_rate(self):
        result = self.industry.run("付费率")
        assert "付费" in result
        assert "%" in result

    def test_retention(self):
        result = self.industry.run("留存")
        assert "D1" in result or "留存" in result

    def test_gacha(self):
        result = self.industry.run("抽卡保底")
        assert "保底" in result or "原神" in result

    def test_dps_formula(self):
        result = self.industry.run("伤害公式")
        assert "DMG" in result or "伤害" in result

    def test_economy(self):
        result = self.industry.run("经济通胀")
        assert "通胀" in result or "经济" in result

    def test_no_match(self):
        result = self.industry.run("quantumphysicsxyz")
        assert "未找到" in result

    def test_empty_query(self):
        result = self.industry.run("")
        assert "错误" in result


# ===================================================================
# Memory Search Tool Tests
# ===================================================================

class TestMemorySearchTool:
    """Tests for the memory search tool (with mocked DiscussionMemory)."""

    def _make_mock_discussion(self, topic, summary="", msg_count=5):
        disc = MagicMock()
        disc.topic = topic
        disc.summary = summary
        disc.created_at = datetime(2024, 6, 15)
        disc.messages = [MagicMock() for _ in range(msg_count)]
        return disc

    def test_search_returns_results(self):
        memory = MagicMock()
        memory.search.return_value = [
            self._make_mock_discussion("抽卡系统设计", "讨论了保底机制"),
            self._make_mock_discussion("战斗公式", "确定了除法型公式"),
        ]
        tool = create_memory_search_tool(memory, "proj-1")
        result = tool.run("抽卡")
        assert "抽卡系统设计" in result
        assert "战斗公式" in result
        memory.search.assert_called_once_with("抽卡", limit=5)

    def test_search_no_results(self):
        memory = MagicMock()
        memory.search.return_value = []
        tool = create_memory_search_tool(memory, "proj-1")
        result = tool.run("不存在的话题")
        assert "未找到" in result

    def test_search_error(self):
        memory = MagicMock()
        memory.search.side_effect = RuntimeError("DB error")
        tool = create_memory_search_tool(memory, "proj-1")
        result = tool.run("测试")
        assert "搜索失败" in result


# ===================================================================
# Read Project Doc Tool Tests
# ===================================================================

class TestReadProjectDocTool:
    """Tests for the project document reader tool."""

    def test_list_no_project(self, tmp_path):
        tool = create_read_project_doc_tool("nonexistent-project")
        with patch("src.crew.tools.Path", side_effect=lambda *a: tmp_path / "data" / "projects"):
            # The tool uses hardcoded "data/projects" path, so test with monkeypatch
            pass
        # Direct test: just verify it handles missing dir gracefully
        result = tool.run(action="list")
        assert "暂无" in result

    def test_read_missing_file(self, tmp_path):
        tool = create_read_project_doc_tool("test-proj")
        result = tool.run(action="read", filename="nonexistent.md")
        assert "不存在" in result

    def test_unknown_action(self):
        tool = create_read_project_doc_tool("test-proj")
        result = tool.run(action="bad_action")
        assert "未知操作" in result

    def test_read_without_filename(self):
        tool = create_read_project_doc_tool("test-proj")
        result = tool.run(action="read")
        assert "请指定" in result


# ===================================================================
# Request Vote Tool Tests
# ===================================================================

class TestRequestVoteTool:
    """Tests for the request vote tool."""

    def test_basic_vote(self):
        ws = MagicMock()
        tool = create_request_vote_tool("disc-1", ws)
        result = tool.run(question="选哪个方案？", options="方案A;方案B;方案C")
        assert "投票已发起" in result
        assert "方案A" in result
        assert "方案B" in result
        assert "方案C" in result

    def test_too_few_options(self):
        ws = MagicMock()
        tool = create_request_vote_tool("disc-1", ws)
        result = tool.run(question="问题", options="只有一个")
        assert "至少需要2个" in result

    def test_too_many_options(self):
        ws = MagicMock()
        tool = create_request_vote_tool("disc-1", ws)
        result = tool.run(question="问题", options="A;B;C;D;E;F;G")
        assert "不能超过6个" in result

    def test_vote_broadcast_failure_graceful(self):
        """Vote should still return result even if broadcast fails."""
        ws = MagicMock()
        tool = create_request_vote_tool("disc-1", ws)
        # broadcast_sync is imported inside the factory, patch at its source
        with patch("src.api.websocket.manager.broadcast_sync", side_effect=RuntimeError("WS down")):
            result = tool.run(question="测试？", options="A;B")
        assert "投票已发起" in result
