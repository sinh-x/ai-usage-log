"""Tests for ProjectService."""

from ai_usage_log.services.project_service import ProjectService


def test_save_project_ref_creates_file(tmp_path):
    svc = ProjectService()
    result = svc.save_project_ref(str(tmp_path), "sinh", "Drgnfly", "# Sessions\n")

    assert result.created is True
    filepath = tmp_path / ".claude" / "ai-sessions-sinh@Drgnfly.md"
    assert filepath.exists()
    assert filepath.read_text() == "# Sessions\n"


def test_save_project_ref_creates_gitignore(tmp_path):
    svc = ProjectService()
    svc.save_project_ref(str(tmp_path), "sinh", "Drgnfly", "# Content")

    gitignore = tmp_path / ".claude" / ".gitignore"
    assert gitignore.exists()
    assert "ai-sessions-*.md" in gitignore.read_text()


def test_save_project_ref_updates_existing(tmp_path):
    svc = ProjectService()
    svc.save_project_ref(str(tmp_path), "sinh", "Drgnfly", "# Original")
    result = svc.save_project_ref(str(tmp_path), "sinh", "Drgnfly", "# Updated")

    assert result.created is False
    filepath = tmp_path / ".claude" / "ai-sessions-sinh@Drgnfly.md"
    assert filepath.read_text() == "# Updated"


def test_save_project_ref_preserves_gitignore(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / ".gitignore").write_text("*.log\n")

    svc = ProjectService()
    svc.save_project_ref(str(tmp_path), "sinh", "Drgnfly", "# Content")

    gitignore_content = (claude_dir / ".gitignore").read_text()
    assert "*.log" in gitignore_content
    assert "ai-sessions-*.md" in gitignore_content


def test_get_project_ref(tmp_path):
    svc = ProjectService()
    svc.save_project_ref(str(tmp_path), "sinh", "Drgnfly", "# Content")

    content = svc.get_project_ref(str(tmp_path), "sinh", "Drgnfly")
    assert content == "# Content"


def test_get_project_ref_missing(tmp_path):
    svc = ProjectService()
    assert svc.get_project_ref(str(tmp_path), "sinh", "Drgnfly") is None
