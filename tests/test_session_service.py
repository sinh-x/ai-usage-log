"""Tests for SessionService."""

from ai_usage_log.services.session_service import SessionService


def test_create_session(tmp_path):
    svc = SessionService(tmp_path)
    result = svc.create_session("2026", "02", "2026-02-15", "claude-code", "# Test Session")

    assert result.is_new is True
    assert len(result.hash) == 6
    assert result.filename.startswith("2026-02-15-")
    assert result.filename.endswith("-claude-code.md")
    assert (tmp_path / "sessions" / "2026" / "02" / result.filename).exists()


def test_update_session(tmp_path):
    svc = SessionService(tmp_path)
    created = svc.create_session("2026", "02", "2026-02-15", "claude-code", "# Original")
    updated = svc.update_session(created.hash, "# Updated", year="2026", month="02")

    assert updated.hash == created.hash
    assert updated.is_new is False

    content = (tmp_path / "sessions" / "2026" / "02" / created.filename).read_text()
    assert content == "# Updated"


def test_update_session_not_found(tmp_path):
    svc = SessionService(tmp_path)
    try:
        svc.update_session("nonexistent", "content")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


def test_get_previous_session(tmp_path):
    svc = SessionService(tmp_path)
    svc.create_session("2026", "02", "2026-02-15", "claude-code", "# Session 1")
    svc.create_session("2026", "02", "2026-02-15", "claude-code", "# Session 2")

    prev = svc.get_previous_session("2026", "02")
    assert prev is not None
    assert prev.content == "# Session 2"


def test_get_previous_session_empty(tmp_path):
    svc = SessionService(tmp_path)
    assert svc.get_previous_session("2026", "02") is None


def test_list_sessions(tmp_path):
    svc = SessionService(tmp_path)
    svc.create_session("2026", "02", "2026-02-14", "claude-code", "# A")
    svc.create_session("2026", "02", "2026-02-15", "cursor", "# B")

    result = svc.list_sessions(year="2026", month="02")
    assert result.count == 2


def test_list_sessions_with_date_filter(tmp_path):
    svc = SessionService(tmp_path)
    svc.create_session("2026", "02", "2026-02-14", "claude-code", "# A")
    svc.create_session("2026", "02", "2026-02-15", "cursor", "# B")

    result = svc.list_sessions(year="2026", month="02", date="2026-02-15")
    assert result.count == 1
    assert result.sessions[0].agent == "cursor"


def test_list_sessions_with_limit(tmp_path):
    svc = SessionService(tmp_path)
    for i in range(5):
        svc.create_session("2026", "02", f"2026-02-{10+i:02d}", "claude-code", f"# {i}")

    result = svc.list_sessions(year="2026", month="02", limit=3)
    assert result.count == 3


def test_find_session_without_year_month(tmp_path):
    svc = SessionService(tmp_path)
    created = svc.create_session("2026", "02", "2026-02-15", "claude-code", "# Test")

    # Find by hash alone
    updated = svc.update_session(created.hash, "# Found it")
    assert updated.hash == created.hash
