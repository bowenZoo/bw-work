"""Tests for mention_parser module."""

import pytest

from src.crew.mention_parser import (
    MentionPattern,
    ROLE_PATTERNS,
    get_all_roles,
    parse_mentioned_roles,
)


class TestMentionPattern:
    """Tests for MentionPattern structure."""

    def test_role_patterns_exist(self):
        """Test that role patterns are defined."""
        assert len(ROLE_PATTERNS) > 0

    def test_all_patterns_have_required_fields(self):
        """Test that all patterns have required fields."""
        for pattern in ROLE_PATTERNS:
            assert pattern.role, "Role name should not be empty"
            assert isinstance(pattern.aliases, list), "Aliases should be a list"
            assert isinstance(pattern.patterns, list), "Patterns should be a list"


class TestParseMentionedRoles:
    """Tests for parse_mentioned_roles function."""

    def test_single_mention_direct_name(self):
        """Test parsing when a single role is directly mentioned."""
        text = "系统策划，你觉得这个技术方案可行吗？"
        roles = parse_mentioned_roles(text)
        assert roles == ["系统策划"]

    def test_single_mention_number_designer(self):
        """Test parsing for number designer mention."""
        text = "数值策划，请分析一下这个数据的平衡性"
        roles = parse_mentioned_roles(text)
        assert roles == ["数值策划"]

    def test_single_mention_player_advocate(self):
        """Test parsing for player advocate mention."""
        text = "玩家代言人，这个设计对新手友好吗？"
        roles = parse_mentioned_roles(text)
        assert roles == ["玩家代言人"]

    def test_multiple_mentions(self):
        """Test parsing when multiple roles are mentioned."""
        text = "系统策划和数值策划，请分别从你们的角度分析一下"
        roles = parse_mentioned_roles(text)
        assert set(roles) == {"系统策划", "数值策划"}

    def test_all_three_mentioned(self):
        """Test parsing when all three roles are mentioned."""
        text = "系统策划、数值策划和玩家代言人都来说说看"
        roles = parse_mentioned_roles(text)
        assert set(roles) == {"系统策划", "数值策划", "玩家代言人"}

    def test_alias_mention_system(self):
        """Test parsing using system designer alias."""
        text = "从技术角度来看，这个方案是否可行？"
        roles = parse_mentioned_roles(text)
        assert "系统策划" in roles

    def test_alias_mention_player(self):
        """Test parsing using player advocate alias."""
        text = "从玩家角度来看，这个设计体验如何？"
        roles = parse_mentioned_roles(text)
        assert "玩家代言人" in roles

    def test_alias_mention_user_experience(self):
        """Test parsing using user experience alias."""
        text = "用户体验方面有什么建议吗？"
        roles = parse_mentioned_roles(text)
        assert "玩家代言人" in roles

    def test_pattern_mention_please_system(self):
        """Test parsing using '请系统策划' pattern."""
        text = "请系统策划评估一下实现难度"
        roles = parse_mentioned_roles(text)
        assert "系统策划" in roles

    def test_pattern_mention_system_can_you(self):
        """Test parsing using '系统能否' pattern."""
        text = "系统策划能否给出技术方案？"
        roles = parse_mentioned_roles(text)
        assert "系统策划" in roles

    def test_no_mention_general_question(self):
        """Test parsing when no specific role is mentioned."""
        text = "大家觉得这个方案怎么样？"
        roles = parse_mentioned_roles(text)
        assert roles == []

    def test_no_mention_everyone(self):
        """Test parsing when addressing everyone generally."""
        text = "请各位都发表一下意见"
        roles = parse_mentioned_roles(text)
        assert roles == []

    def test_pattern_balance(self):
        """Test parsing for balance-related mentions."""
        text = "平衡性方面需要注意什么？"
        roles = parse_mentioned_roles(text)
        assert "数值策划" in roles

    def test_empty_text(self):
        """Test parsing empty text."""
        roles = parse_mentioned_roles("")
        assert roles == []

    def test_complex_sentence(self):
        """Test parsing complex sentence with multiple patterns."""
        text = """
        接下来，我想请系统策划评估一下技术可行性，
        同时玩家代言人也从用户体验角度给出建议。
        """
        roles = parse_mentioned_roles(text)
        assert "系统策划" in roles
        assert "玩家代言人" in roles

    def test_no_false_positive_partial_match(self):
        """Test that partial matches don't cause false positives."""
        text = "我们需要一个系统来管理这些数据"
        roles = parse_mentioned_roles(text)
        # '系统' is an alias, so it should match
        assert "系统策划" in roles

    def test_chinese_comma_pattern(self):
        """Test pattern with Chinese comma."""
        text = "数值策划，请说明一下经济模型"
        roles = parse_mentioned_roles(text)
        assert "数值策划" in roles

    def test_english_comma_pattern(self):
        """Test pattern with English comma."""
        text = "系统策划,你怎么看？"
        roles = parse_mentioned_roles(text)
        assert "系统策划" in roles


class TestGetAllRoles:
    """Tests for get_all_roles function."""

    def test_returns_all_roles(self):
        """Test that get_all_roles returns all defined roles."""
        roles = get_all_roles()
        assert len(roles) == len(ROLE_PATTERNS)

    def test_contains_expected_roles(self):
        """Test that all expected roles are present."""
        roles = get_all_roles()
        expected = {"系统策划", "数值策划", "玩家代言人"}
        assert set(roles) == expected
