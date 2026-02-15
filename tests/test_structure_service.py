"""Tests for StructureService."""

from ai_usage_log.services.structure_service import StructureService


def test_init_structure_creates_dirs(tmp_path):
    base = tmp_path / "ai-usage"
    svc = StructureService(base)
    result = svc.init_structure("2026", "02")

    assert (base / "sessions" / "2026" / "02").is_dir()
    assert (base / "daily" / "2026" / "02").is_dir()
    assert (base / "insights" / "weekly").is_dir()
    assert (base / "insights" / "monthly").is_dir()
    assert not result.already_existed


def test_init_structure_creates_tracking_files(tmp_path):
    base = tmp_path / "ai-usage"
    svc = StructureService(base)
    result = svc.init_structure("2026", "02")

    assert (base / "learning-queue.md").exists()
    assert (base / "skills-gained.md").exists()
    assert (base / "statistics.md").exists()
    assert (base / "verification-queue.md").exists()
    assert (base / "quiz-bank.md").exists()
    assert len(result.created_files) == 5


def test_init_structure_idempotent(tmp_path):
    base = tmp_path / "ai-usage"
    svc = StructureService(base)
    svc.init_structure("2026", "02")
    result2 = svc.init_structure("2026", "02")

    assert result2.already_existed is True
    assert len(result2.created_dirs) == 0
    assert len(result2.created_files) == 0
