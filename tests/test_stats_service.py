"""Tests for StatsService."""

from pathlib import Path

from ai_usage_log.services.stats_service import StatsService, _extract_field, _parse_duration_to_minutes


def _create_session_file(base: Path, year: str, month: str, date: str, hash: str, agent: str, content: str = "# Session"):
    """Helper to create a session file on disk."""
    d = base / "sessions" / year / month
    d.mkdir(parents=True, exist_ok=True)
    filepath = d / f"{date}-{hash}-{agent}.md"
    filepath.write_text(content)
    return filepath


def test_empty_dir(tmp_path):
    svc = StatsService(tmp_path)
    result = svc.compute_stats()
    assert result.total_sessions == 0
    assert result.total_agents == 0
    assert result.by_month == []
    assert result.by_agent == []


def test_no_sessions_dir(tmp_path):
    svc = StatsService(tmp_path)
    result = svc.compute_stats()
    assert result.total_sessions == 0


def test_basic_counts(tmp_path):
    _create_session_file(tmp_path, "2026", "02", "2026-02-10", "aaa111", "claude-code")
    _create_session_file(tmp_path, "2026", "02", "2026-02-11", "bbb222", "cursor")
    _create_session_file(tmp_path, "2026", "02", "2026-02-11", "ccc333", "claude-code")

    svc = StatsService(tmp_path)
    result = svc.compute_stats()

    assert result.total_sessions == 3
    assert result.total_agents == 2
    assert result.total_active_days == 2
    assert result.sessions_by_agent == {"claude-code": 2, "cursor": 1}
    assert result.date_range == "2026-02-10 to 2026-02-11"


def test_year_filter(tmp_path):
    _create_session_file(tmp_path, "2025", "12", "2025-12-25", "aaa111", "claude-code")
    _create_session_file(tmp_path, "2026", "01", "2026-01-05", "bbb222", "claude-code")

    svc = StatsService(tmp_path)
    result = svc.compute_stats(year="2026")

    assert result.total_sessions == 1
    assert result.date_range == "2026-01-05"


def test_month_filter(tmp_path):
    _create_session_file(tmp_path, "2026", "01", "2026-01-05", "aaa111", "claude-code")
    _create_session_file(tmp_path, "2026", "02", "2026-02-10", "bbb222", "claude-code")
    _create_session_file(tmp_path, "2026", "02", "2026-02-11", "ccc333", "cursor")

    svc = StatsService(tmp_path)
    result = svc.compute_stats(year="2026", month="02")

    assert result.total_sessions == 2
    assert result.total_agents == 2


def test_monthly_breakdown(tmp_path):
    _create_session_file(tmp_path, "2026", "01", "2026-01-05", "aaa111", "claude-code")
    _create_session_file(tmp_path, "2026", "02", "2026-02-10", "bbb222", "cursor")

    svc = StatsService(tmp_path)
    result = svc.compute_stats()

    assert len(result.by_month) == 2
    assert result.by_month[0].month == "2026-01"
    assert result.by_month[0].session_count == 1
    assert result.by_month[1].month == "2026-02"
    assert result.by_month[1].sessions_by_agent == {"cursor": 1}


def test_agent_breakdown(tmp_path):
    _create_session_file(tmp_path, "2026", "02", "2026-02-10", "aaa111", "claude-code")
    _create_session_file(tmp_path, "2026", "02", "2026-02-11", "bbb222", "claude-code")
    _create_session_file(tmp_path, "2026", "02", "2026-02-12", "ccc333", "cursor")

    svc = StatsService(tmp_path)
    result = svc.compute_stats()

    agent_map = {a.agent: a for a in result.by_agent}
    assert agent_map["claude-code"].session_count == 2
    assert set(agent_map["claude-code"].dates) == {"2026-02-10", "2026-02-11"}
    assert agent_map["cursor"].session_count == 1


def test_header_parsing_multiline(tmp_path):
    content = """\
# Session Log

> Date: 2026-02-10
> Duration: ~45 minutes
> Project: ai-usage-log
> Agent: Claude Code (claude-code)

## Summary
Did some stuff.
"""
    _create_session_file(tmp_path, "2026", "02", "2026-02-10", "aaa111", "claude-code", content)

    svc = StatsService(tmp_path)
    result = svc.compute_stats(include_headers=True)

    assert result.total_sessions == 1
    assert result.total_duration_minutes == 45.0
    assert result.projects == ["ai-usage-log"]


def test_header_parsing_compressed(tmp_path):
    content = """\
# Session Log

> **Date:** 2026-02-10 | **Duration:** ~2 hours | **Project:** my-project
> **Agent:** Claude Code

## Summary
"""
    _create_session_file(tmp_path, "2026", "02", "2026-02-10", "aaa111", "claude-code", content)

    svc = StatsService(tmp_path)
    result = svc.compute_stats(include_headers=True)

    assert result.total_duration_minutes == 120.0
    assert result.projects == ["my-project"]


def test_header_no_duration(tmp_path):
    content = """\
# Session Log

> Date: 2026-02-10
> Project: foo

## Summary
"""
    _create_session_file(tmp_path, "2026", "02", "2026-02-10", "aaa111", "claude-code", content)

    svc = StatsService(tmp_path)
    result = svc.compute_stats(include_headers=True)

    assert result.total_duration_minutes is None
    assert result.projects == ["foo"]


def test_multi_agent_multi_month(tmp_path):
    _create_session_file(tmp_path, "2025", "12", "2025-12-01", "a11111", "claude-code")
    _create_session_file(tmp_path, "2025", "12", "2025-12-15", "b22222", "cursor")
    _create_session_file(tmp_path, "2026", "01", "2026-01-05", "c33333", "claude-code")
    _create_session_file(tmp_path, "2026", "02", "2026-02-10", "d44444", "windsurf")

    svc = StatsService(tmp_path)
    result = svc.compute_stats()

    assert result.total_sessions == 4
    assert result.total_agents == 3
    assert len(result.by_month) == 3
    assert result.sessions_by_agent == {"claude-code": 2, "cursor": 1, "windsurf": 1}


def test_projects_none_without_headers(tmp_path):
    _create_session_file(tmp_path, "2026", "02", "2026-02-10", "aaa111", "claude-code")

    svc = StatsService(tmp_path)
    result = svc.compute_stats(include_headers=False)

    assert result.projects is None
    assert result.total_duration_minutes is None


def test_duration_aggregation(tmp_path):
    for i, (hash, dur) in enumerate([("aa1111", "~30 minutes"), ("bb2222", "~1.5 hours")]):
        content = f"# Session\n\n> Duration: {dur}\n\n## Summary\n"
        _create_session_file(tmp_path, "2026", "02", f"2026-02-{10+i:02d}", hash, "claude-code", content)

    svc = StatsService(tmp_path)
    result = svc.compute_stats(include_headers=True)

    assert result.total_duration_minutes == 120.0  # 30 + 90


# --- Unit tests for helper functions ---


def test_parse_duration_minutes():
    assert _parse_duration_to_minutes("~30 minutes") == 30.0
    assert _parse_duration_to_minutes("~45 mins") == 45.0
    assert _parse_duration_to_minutes("~1 min") == 1.0


def test_parse_duration_hours():
    assert _parse_duration_to_minutes("~2 hours") == 120.0
    assert _parse_duration_to_minutes("~1.5 hours") == 90.0
    assert _parse_duration_to_minutes("~1 hour") == 60.0


def test_parse_duration_invalid():
    assert _parse_duration_to_minutes("unknown") is None
    assert _parse_duration_to_minutes("") is None


def test_extract_field_plain():
    assert _extract_field("Duration: ~30 minutes", "Duration") == "~30 minutes"
    assert _extract_field("Project: my-project", "Project") == "my-project"


def test_extract_field_bold():
    assert _extract_field("**Duration:** ~2 hours | **Project:** foo", "Duration") == "~2 hours"
    assert _extract_field("**Duration:** ~2 hours | **Project:** foo", "Project") == "foo"


def test_extract_field_missing():
    assert _extract_field("something else entirely", "Duration") is None


def test_active_days_per_month(tmp_path):
    _create_session_file(tmp_path, "2026", "02", "2026-02-10", "aaa111", "claude-code")
    _create_session_file(tmp_path, "2026", "02", "2026-02-10", "bbb222", "cursor")
    _create_session_file(tmp_path, "2026", "02", "2026-02-11", "ccc333", "claude-code")

    svc = StatsService(tmp_path)
    result = svc.compute_stats()

    assert result.by_month[0].active_days == 2
