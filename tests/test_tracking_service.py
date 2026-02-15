"""Tests for TrackingService."""

from ai_usage_log.services.tracking_service import TrackingService


def test_update_tracking(tmp_path):
    svc = TrackingService(tmp_path)
    result = svc.update_tracking({
        "statistics.md": "# Updated Stats",
        "skills-gained.md": "# Updated Skills",
    })

    assert set(result.updated_files) == {"statistics.md", "skills-gained.md"}
    assert (tmp_path / "statistics.md").read_text() == "# Updated Stats"
    assert (tmp_path / "skills-gained.md").read_text() == "# Updated Skills"


def test_update_tracking_ignores_invalid(tmp_path):
    svc = TrackingService(tmp_path)
    result = svc.update_tracking({
        "statistics.md": "# Valid",
        "evil-file.md": "# Invalid",
    })

    assert result.updated_files == ["statistics.md"]
    assert not (tmp_path / "evil-file.md").exists()


def test_get_stats_empty(tmp_path):
    svc = TrackingService(tmp_path)
    result = svc.get_stats()
    assert result.content == ""


def test_get_stats_existing(tmp_path):
    (tmp_path / "statistics.md").write_text("# Stats\n- Total: 5")
    svc = TrackingService(tmp_path)
    result = svc.get_stats()
    assert "Total: 5" in result.content


def test_get_tracking_file(tmp_path):
    (tmp_path / "quiz-bank.md").write_text("# Quiz")
    svc = TrackingService(tmp_path)
    content = svc.get_tracking_file("quiz-bank.md")
    assert content == "# Quiz"


def test_get_tracking_file_invalid(tmp_path):
    svc = TrackingService(tmp_path)
    try:
        svc.get_tracking_file("bad-file.md")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
