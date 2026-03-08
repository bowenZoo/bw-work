"""Test that run_document_centric executes agents sequentially and pauses
immediately when any agent @超级制作人.

Strategy: extract the sequential agent loop and test it directly,
bypassing the heavy setup of run_document_centric.
"""

import time
import threading
from unittest.mock import MagicMock, patch

import pytest

from src.crew.discussion_crew import AgentStatus


# ---------------------------------------------------------------------------
# Minimal crew stub
# ---------------------------------------------------------------------------

class _MinimalCrew:
    """Minimal stub with just the methods the sequential loop calls."""

    def __init__(self):
        self._discussion_id = "test-disc"
        self._abort_reason = None
        self._producer_questions_this_round = False
        self._call_log: list[tuple[str, float]] = []

        self._broadcast_status = MagicMock(side_effect=self._log_broadcast_status)
        self._broadcast_message = MagicMock(side_effect=self._log_broadcast_message)
        self._record_message = MagicMock()
        self._wait_for_producer_decision = MagicMock(return_value=[])
        self._inject_user_messages = MagicMock()
        self._has_pending_producer_messages = MagicMock(return_value=False)

    def _log_broadcast_status(self, role, status):
        self._call_log.append((f"status:{role}:{status}", time.monotonic()))

    def _log_broadcast_message(self, role, content):
        self._call_log.append((f"msg:{role}", time.monotonic()))
        # Simulate @超级制作人 detection inside _broadcast_message
        if "@超级制作人" in content:
            self._producer_questions_this_round = True
            self._call_log.append(("super_producer_triggered", time.monotonic()))

    def _run_sequential_loop(self, agents_to_call):
        """Extracted verbatim from run_document_centric sequential block."""
        round_responses: list[tuple[str, str]] = []
        was_interrupted = False
        pending_injected: list = []

        for _seq_agent in agents_to_call:
            if self._abort_reason:
                was_interrupted = True
                break

            context = "mock_context"

            self._broadcast_status(_seq_agent.role, AgentStatus.THINKING)
            try:
                from src.crew.tools import set_tool_context, clear_tool_context
                set_tool_context(self._discussion_id, _seq_agent.role_name)
            except Exception:
                pass
            try:
                _seq_response = _seq_agent.respond_sync(context)
            except Exception as exc:
                _seq_response = f"（{_seq_agent.role}暂时无法给出回复）"
            finally:
                try:
                    from src.crew.tools import clear_tool_context
                    clear_tool_context()
                except Exception:
                    pass

            self._broadcast_status(_seq_agent.role, AgentStatus.SPEAKING)
            self._broadcast_message(_seq_agent.role, _seq_response)
            self._record_message(_seq_agent.role, _seq_response)
            self._broadcast_status(_seq_agent.role, AgentStatus.IDLE)
            round_responses.append((_seq_agent.role, _seq_response))

            if self._producer_questions_this_round:
                self._producer_questions_this_round = False
                was_interrupted = True
                _producer_replies = self._wait_for_producer_decision()
                if self._abort_reason:
                    break
                if _producer_replies:
                    self._inject_user_messages(_producer_replies)
                    pending_injected.extend(_producer_replies)
                was_interrupted = False

            if self._has_pending_producer_messages():
                was_interrupted = True
                break

        return round_responses, was_interrupted


def _make_agent(role: str, response: str, delay: float = 0.0):
    agent = MagicMock()
    agent.role = role
    agent.role_name = role

    def respond_sync(ctx):
        if delay:
            time.sleep(delay)
        return response
    agent.respond_sync.side_effect = respond_sync
    return agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSequentialExecution:

    # ------------------------------------------------------------------
    # Test 1: strict sequential order (A finishes before B starts)
    # ------------------------------------------------------------------
    def test_agents_run_in_order(self):
        """Agent B must not start before agent A's respond_sync returns."""
        crew = _MinimalCrew()
        call_times: dict[str, float] = {}

        agent_a = _make_agent("A角色", "A的发言", delay=0.05)
        agent_b = _make_agent("B角色", "B的发言", delay=0.0)

        orig_a = agent_a.respond_sync.side_effect
        orig_b = agent_b.respond_sync.side_effect

        def track_a(ctx):
            result = orig_a(ctx)
            call_times["A_end"] = time.monotonic()
            return result

        def track_b(ctx):
            call_times["B_start"] = time.monotonic()
            return orig_b(ctx)

        agent_a.respond_sync.side_effect = track_a
        agent_b.respond_sync.side_effect = track_b

        crew._run_sequential_loop([agent_a, agent_b])

        assert "A_end" in call_times, "Agent A never completed"
        assert "B_start" in call_times, "Agent B never started"
        assert call_times["A_end"] <= call_times["B_start"], (
            f"PARALLEL: B started ({call_times['B_start']:.4f}) "
            f"before A finished ({call_times['A_end']:.4f})"
        )

    # ------------------------------------------------------------------
    # Test 2: @超级制作人 triggers wait BEFORE next agent starts
    # ------------------------------------------------------------------
    def test_super_producer_mention_pauses_before_next_agent(self):
        """When agent A @超级制作人, _wait_for_producer_decision is called
        before agent B's respond_sync is invoked."""
        crew = _MinimalCrew()
        event_times: dict[str, float] = {}

        agent_a = _make_agent("A角色", "有个战略问题 @超级制作人：继续还是转型？")
        agent_b = _make_agent("B角色", "B的正常发言")

        orig_wait = crew._wait_for_producer_decision.side_effect
        def track_wait():
            event_times["wait_called"] = time.monotonic()
            return []
        crew._wait_for_producer_decision.side_effect = track_wait

        orig_b = agent_b.respond_sync.side_effect
        def track_b(ctx):
            event_times["B_start"] = time.monotonic()
            return orig_b(ctx)
        agent_b.respond_sync.side_effect = track_b

        crew._run_sequential_loop([agent_a, agent_b])

        assert crew._wait_for_producer_decision.called, \
            "_wait_for_producer_decision was NEVER called — @超级制作人 not detected"
        assert "B_start" in event_times, "Agent B never ran"
        assert "wait_called" in event_times, "_wait_for_producer_decision was not tracked"

        assert event_times["wait_called"] <= event_times["B_start"], (
            f"B started ({event_times['B_start']:.5f}) BEFORE wait "
            f"({event_times['wait_called']:.5f}) — pause not working!"
        )

    # ------------------------------------------------------------------
    # Test 3: without @超级制作人, all agents speak and no wait
    # ------------------------------------------------------------------
    def test_all_agents_speak_no_trigger(self):
        """All agents run and _wait_for_producer_decision is NOT called."""
        crew = _MinimalCrew()
        agents = [_make_agent(f"角色{i}", f"角色{i}的正常发言") for i in range(4)]

        responses, was_interrupted = crew._run_sequential_loop(agents)

        assert len(responses) == 4, f"Expected 4 responses, got {len(responses)}"
        for agent in agents:
            agent.respond_sync.assert_called_once()
        assert not crew._wait_for_producer_decision.called
        assert not was_interrupted

    # ------------------------------------------------------------------
    # Test 4: only the triggering agent's question goes through;
    # the next agent still runs after producer replies
    # ------------------------------------------------------------------
    def test_subsequent_agent_runs_after_producer_reply(self):
        """After _wait_for_producer_decision returns, agent B still speaks."""
        crew = _MinimalCrew()

        agent_a = _make_agent("A角色", "有问题 @超级制作人：问题X")
        agent_b = _make_agent("B角色", "B的后续发言")

        crew._wait_for_producer_decision.return_value = [
            {"role": "制作人", "content": "我的答案是Y"}
        ]

        responses, was_interrupted = crew._run_sequential_loop([agent_a, agent_b])

        # Both agents should have responded
        roles = [r for r, _ in responses]
        assert "A角色" in roles
        assert "B角色" in roles
        assert not was_interrupted

        # inject_user_messages was called with the producer reply
        crew._inject_user_messages.assert_called_once()

    # ------------------------------------------------------------------
    # Test 5: multiple @超级制作人 (one per agent) each pause separately
    # ------------------------------------------------------------------
    def test_multiple_agents_each_pause_separately(self):
        """If A and B both @超级制作人, there should be TWO separate waits."""
        crew = _MinimalCrew()

        agent_a = _make_agent("A角色", "@超级制作人：问题A")
        agent_b = _make_agent("B角色", "@超级制作人：问题B")
        agent_c = _make_agent("C角色", "C的普通发言")

        wait_count = [0]
        def count_wait():
            wait_count[0] += 1
            return []
        crew._wait_for_producer_decision.side_effect = count_wait

        responses, _ = crew._run_sequential_loop([agent_a, agent_b, agent_c])

        assert wait_count[0] == 2, (
            f"Expected 2 waits (one per @超级制作人), got {wait_count[0]}"
        )
        assert len(responses) == 3
