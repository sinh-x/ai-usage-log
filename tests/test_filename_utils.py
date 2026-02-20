"""Tests for the shared filename parser."""

from ai_usage_log.utils.filename import parse_session_filename


def test_standard_filename():
    result = parse_session_filename("2026-02-15-abc123-claude-code.md")
    assert result == ("2026-02-15", "abc123", "claude-code")


def test_single_word_agent():
    result = parse_session_filename("2026-01-10-f0f0f0-cursor.md")
    assert result == ("2026-01-10", "f0f0f0", "cursor")


def test_agent_with_multiple_dashes():
    result = parse_session_filename("2025-12-25-aabbcc-my-custom-agent.md")
    assert result == ("2025-12-25", "aabbcc", "my-custom-agent")


def test_not_markdown():
    assert parse_session_filename("2026-02-15-abc123-claude-code.txt") is None


def test_too_few_parts():
    assert parse_session_filename("2026-02-15.md") is None
    assert parse_session_filename("2026-02-15-abc.md") is None


def test_empty_string():
    assert parse_session_filename("") is None


def test_no_extension():
    assert parse_session_filename("2026-02-15-abc123-agent") is None
