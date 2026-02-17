"""Tests for config/settings.py."""

import os
from pathlib import Path
from unittest.mock import patch

from ai_usage_log.config.settings import (
    detect_project,
    get_base_path,
    get_host,
    get_terminal_session,
    get_today,
    get_tz_offset,
    get_user,
    get_year_month,
)


def test_get_base_path_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AI_USAGE_LOG_PATH", None)
        result = get_base_path()
        assert result == Path.home() / "Documents" / "ai-usage"


def test_get_base_path_custom():
    with patch.dict(os.environ, {"AI_USAGE_LOG_PATH": "/tmp/test-logs"}):
        result = get_base_path()
        assert result == Path("/tmp/test-logs")


def test_get_user():
    with patch.dict(os.environ, {"USER": "testuser"}):
        assert get_user() == "testuser"


def test_get_host():
    result = get_host()
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_terminal_session_standalone():
    env = {k: v for k, v in os.environ.items() if k not in ("ZELLIJ", "TMUX", "STY")}
    with patch.dict(os.environ, env, clear=True):
        assert get_terminal_session() == "standalone"


def test_get_terminal_session_zellij():
    with patch.dict(os.environ, {"ZELLIJ": "1", "ZELLIJ_SESSION_NAME": "dev"}, clear=False):
        assert get_terminal_session() == "zellij:dev"


def test_get_today():
    result = get_today()
    assert len(result) == 10  # YYYY-MM-DD
    assert result[4] == "-" and result[7] == "-"


def test_get_year_month():
    year, month = get_year_month()
    assert len(year) == 4
    assert len(month) == 2


def test_detect_project_non_git(tmp_path):
    result = detect_project(str(tmp_path))
    assert result is None


def test_get_tz_offset_from_env():
    with patch.dict(os.environ, {"AI_USAGE_LOG_TZ_OFFSET": "7"}):
        assert get_tz_offset() == 7


def test_get_tz_offset_negative():
    with patch.dict(os.environ, {"AI_USAGE_LOG_TZ_OFFSET": "-5"}):
        assert get_tz_offset() == -5


def test_get_tz_offset_auto_detect():
    """Without env var, should auto-detect from system timezone."""
    env = {k: v for k, v in os.environ.items() if k != "AI_USAGE_LOG_TZ_OFFSET"}
    with patch.dict(os.environ, env, clear=True):
        result = get_tz_offset()
        assert isinstance(result, int)
        assert -12 <= result <= 14
