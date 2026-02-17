"""Tests for SessionService and batch tools."""

from ai_usage_log.services.project_service import ProjectService
from ai_usage_log.services.session_service import SessionService
from ai_usage_log.services.structure_service import StructureService
from ai_usage_log.services.tracking_service import TrackingService


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


# --- Batch tool integration tests ---


def test_prepare_session_components(tmp_path):
    """Test the components that prepare_session combines."""
    structure_svc = StructureService(tmp_path)
    session_svc = SessionService(tmp_path)
    tracking_svc = TrackingService(tmp_path)

    # 1. Init structure
    structure = structure_svc.init_structure("2026", "02")
    assert str(tmp_path) in structure.base_path

    # 2. Create a session so get_previous works
    session_svc.create_session("2026", "02", "2026-02-15", "claude-code", "# Previous")

    # 3. Get previous session
    prev = session_svc.get_previous_session("2026", "02")
    assert prev is not None
    assert prev.content == "# Previous"

    # 4. Get stats
    stats = tracking_svc.get_stats()
    assert stats.path.endswith("statistics.md")


def test_save_session_bundle_components(tmp_path):
    """Test the components that save_session_bundle combines."""
    session_svc = SessionService(tmp_path)
    tracking_svc = TrackingService(tmp_path)
    project_svc = ProjectService()

    # Ensure tracking dir exists
    tmp_path.mkdir(parents=True, exist_ok=True)

    # 1. Create session
    session_result = session_svc.create_session(
        "2026", "02", "2026-02-17", "claude-code", "# Bundle test"
    )
    assert session_result.is_new is True
    assert len(session_result.hash) == 6

    # 2. Update tracking
    tracking_result = tracking_svc.update_tracking({
        "statistics.md": "# Stats\nSessions: 1",
    })
    assert "statistics.md" in tracking_result.updated_files

    # 3. Save project ref
    project_root = str(tmp_path / "my-project")
    (tmp_path / "my-project").mkdir()
    ref_result = project_svc.save_project_ref(
        project_root, "sinh", "Drgnfly", "# AI Sessions\n| row |"
    )
    assert ref_result.created is True


def test_save_session_bundle_optional_fields(tmp_path):
    """save_session_bundle should work with only session (no tracking, no project ref)."""
    session_svc = SessionService(tmp_path)

    result = session_svc.create_session(
        "2026", "02", "2026-02-17", "claude-code", "# Minimal"
    )
    assert result.is_new is True

    # Verify no error when tracking/project_ref are None
    from ai_usage_log.models.schemas import SaveBundleResult

    bundle = SaveBundleResult(session=result, tracking=None, project_ref=None)
    assert bundle.tracking is None
    assert bundle.project_ref is None
