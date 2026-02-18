"""Tests for utils.content — resolve_content."""

import pytest

from ai_usage_log.utils.content import resolve_content


def test_inline_content():
    assert resolve_content("hello", "") == "hello"


def test_content_path(tmp_path):
    f = tmp_path / "session.md"
    f.write_text("# Session\nBody here")
    assert resolve_content("", str(f)) == "# Session\nBody here"


def test_content_path_takes_precedence(tmp_path):
    f = tmp_path / "session.md"
    f.write_text("from file")
    assert resolve_content("inline ignored", str(f)) == "from file"


def test_both_empty_raises():
    with pytest.raises(ValueError, match="must be provided"):
        resolve_content("", "")


def test_content_path_not_found():
    with pytest.raises(FileNotFoundError, match="does not exist"):
        resolve_content("", "/nonexistent/file.md")
