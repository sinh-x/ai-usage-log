"""Integration tests using real Claude JSONL session files.

These tests validate the parser against actual session data to catch
discrepancies that synthetic tests might miss.
"""

from pathlib import Path

import pytest

from ai_usage_log.services.claude_session_service import ClaudeSessionService

# Real session used as reference fixture
_SESSION_ID = "8a25fee9-e58d-4953-8163-0191907744e0"
_CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
_SESSION_FILE = _CLAUDE_PROJECTS_DIR / "-home-sinh--claude" / f"{_SESSION_ID}.jsonl"


@pytest.mark.skipif(
    not _SESSION_FILE.is_file(),
    reason=f"Real session file not found: {_SESSION_FILE}",
)
class TestRealSession8a25fee9:
    """Tests against real session 8a25fee9 to validate token invariants."""

    @pytest.fixture(autouse=True)
    def _parse_session(self):
        svc = ClaudeSessionService()
        self.data = svc.read_session(_SESSION_ID)

    def test_per_turn_tokens_sum_matches_session_totals(self):
        """Core invariant: sum of per-turn tokens == session-level totals."""
        data = self.data

        turn_input = sum(t.tokens.input_tokens for t in data.conversation)
        turn_output = sum(t.tokens.output_tokens for t in data.conversation)
        turn_cache_r = sum(t.tokens.cache_read_tokens for t in data.conversation)
        turn_cache_c = sum(t.tokens.cache_creation_tokens for t in data.conversation)

        assert turn_input == data.input_tokens, (
            f"input_tokens: turns={turn_input} != session={data.input_tokens}"
        )
        assert turn_output == data.output_tokens, (
            f"output_tokens: turns={turn_output} != session={data.output_tokens}"
        )
        assert turn_cache_r == data.cache_read_tokens, (
            f"cache_read: turns={turn_cache_r} != session={data.cache_read_tokens}"
        )
        assert turn_cache_c == data.cache_creation_tokens, (
            f"cache_creation: turns={turn_cache_c} != session={data.cache_creation_tokens}"
        )

    def test_every_turn_has_tokens(self):
        """Every conversation turn should have a tokens object."""
        for i, turn in enumerate(self.data.conversation):
            assert turn.tokens is not None, f"Turn {i} has no tokens"

    def test_session_has_expected_shape(self):
        """Sanity check: session has conversations, tokens, and tools."""
        data = self.data
        assert len(data.conversation) > 0
        assert data.total_tokens > 0
        assert data.total_assistant_messages > 0
        assert data.total_user_messages > 0
