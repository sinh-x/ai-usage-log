"""Tests for JsonlStatsService."""

import json
import time


from ai_usage_log.services.claude_session_service import ClaudeSessionService
from ai_usage_log.services.jsonl_stats_service import JsonlStatsService


# --- Helpers (reused from test_claude_session_service.py) ---


def _user_entry(content, timestamp="2026-02-15T10:00:00.000Z", git_branch="main"):
    return {
        "type": "user",
        "timestamp": timestamp,
        "gitBranch": git_branch,
        "message": {"role": "user", "content": content},
    }


def _assistant_entry(
    content_blocks,
    timestamp="2026-02-15T10:01:00.000Z",
    model="claude-opus-4-6",
    input_tokens=100,
    output_tokens=50,
    cache_read=0,
    cache_creation=0,
    message_id=None,
):
    entry = {
        "type": "assistant",
        "timestamp": timestamp,
        "message": {
            "role": "assistant",
            "model": model,
            "content": content_blocks,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
            },
        },
    }
    if message_id:
        entry["message"]["id"] = message_id
    return entry


def _text_block(text):
    return {"type": "text", "text": text}


def _tool_use_block(name, tool_input=None):
    return {"type": "tool_use", "name": name, "input": tool_input or {}}


def _write_jsonl(path, entries):
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _setup_project(tmp_path, project_path="/home/user/myproject", session_id="abc-123", entries=None):
    encoded = ClaudeSessionService.encode_project_path(project_path)
    proj_dir = tmp_path / "projects" / encoded
    proj_dir.mkdir(parents=True, exist_ok=True)
    if entries is not None:
        _write_jsonl(proj_dir / f"{session_id}.jsonl", entries)
    return proj_dir


def _make_service(tmp_path):
    """Create a JsonlStatsService with temp dirs."""
    stats_dir = tmp_path / "statistics"
    stats_dir.mkdir(parents=True, exist_ok=True)
    claude_svc = ClaudeSessionService(claude_projects_dir=tmp_path / "projects")
    return JsonlStatsService(statistics_dir=stats_dir, claude_session_service=claude_svc)


def _basic_entries(
    timestamp_start="2026-02-15T10:00:00.000Z",
    timestamp_end="2026-02-15T10:01:00.000Z",
    model="claude-opus-4-6",
    input_tokens=100,
    output_tokens=50,
    cache_read=200,
    cache_creation=300,
    git_branch="main",
):
    return [
        _user_entry("Hello", timestamp=timestamp_start, git_branch=git_branch),
        _assistant_entry(
            [_text_block("Hi there"), _tool_use_block("Read", {"file_path": "/tmp/a.py"})],
            timestamp=timestamp_end,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read=cache_read,
            cache_creation=cache_creation,
        ),
    ]


# --- Tests ---


class TestExtractCreatesCache:
    def test_extract_creates_cache_file(self, tmp_path):
        """JSON file should appear at statistics/{date}--{proj}--{id}.json."""
        entries = _basic_entries()
        _setup_project(tmp_path, "/home/user/myproject", "sess-001", entries)
        svc = _make_service(tmp_path)

        svc.extract_session_stats("sess-001", "/home/user/myproject")

        cache_files = list((tmp_path / "statistics").glob("*.json"))
        assert len(cache_files) == 1
        assert "sess-001" in cache_files[0].name


class TestExtractCorrectStats:
    def test_extract_correct_stats(self, tmp_path):
        """All fields should match read_session output."""
        entries = _basic_entries()
        _setup_project(tmp_path, "/home/user/myproject", "sess-002", entries)
        svc = _make_service(tmp_path)

        stats = svc.extract_session_stats("sess-002", "/home/user/myproject")

        assert stats.session_id == "sess-002"
        assert stats.project_name == "myproject"
        assert stats.input_tokens == 100
        assert stats.output_tokens == 50
        assert stats.cache_read_tokens == 200
        assert stats.cache_creation_tokens == 300
        assert stats.total_user_messages == 1
        assert stats.total_assistant_messages == 1
        assert stats.total_tool_calls == 1
        assert stats.duration_minutes == 1.0
        assert stats.model == "claude-opus-4-6"
        assert stats.git_branch == "main"
        assert stats.tools_summary == {"Read": 1}


class TestCacheHit:
    def test_cache_hit(self, tmp_path):
        """Second call should read from disk cache, not JSONL."""
        entries = _basic_entries()
        _setup_project(tmp_path, "/home/user/myproject", "sess-003", entries)
        svc = _make_service(tmp_path)

        # First call — parses JSONL
        stats1 = svc.extract_session_stats("sess-003", "/home/user/myproject")

        # Verify cache is used on second call (same mtime = cache hit)
        stats2 = svc.extract_session_stats("sess-003", "/home/user/myproject")

        assert stats1.session_id == stats2.session_id
        assert stats1.input_tokens == stats2.input_tokens
        assert stats1.jsonl_mtime == stats2.jsonl_mtime


class TestCacheInvalidation:
    def test_cache_invalidation(self, tmp_path):
        """Append to JSONL -> re-parse on next call."""
        entries = _basic_entries()
        proj_dir = _setup_project(tmp_path, "/home/user/myproject", "sess-004", entries)
        svc = _make_service(tmp_path)

        stats1 = svc.extract_session_stats("sess-004", "/home/user/myproject")
        assert stats1.total_user_messages == 1

        # Append another user+assistant turn
        time.sleep(0.05)  # Ensure mtime changes
        jsonl_file = proj_dir / "sess-004.jsonl"
        with open(jsonl_file, "a") as f:
            f.write(json.dumps(_user_entry("Follow up", timestamp="2026-02-15T10:02:00.000Z")) + "\n")
            f.write(json.dumps(_assistant_entry(
                [_text_block("Sure")],
                timestamp="2026-02-15T10:03:00.000Z",
                input_tokens=50,
                output_tokens=25,
            )) + "\n")

        stats2 = svc.extract_session_stats("sess-004", "/home/user/myproject")
        assert stats2.total_user_messages == 2
        assert stats2.input_tokens == 150  # 100 + 50


class TestCacheCorruptFallback:
    def test_cache_corrupt_fallback(self, tmp_path):
        """Bad JSON in cache -> fresh parse."""
        entries = _basic_entries()
        _setup_project(tmp_path, "/home/user/myproject", "sess-005", entries)
        svc = _make_service(tmp_path)

        # Create corrupt cache file
        stats_dir = tmp_path / "statistics"
        corrupt_file = stats_dir / "2026-02-15--myproject--sess-005.json"
        corrupt_file.write_text("{ invalid json }")

        # Should still parse successfully
        stats = svc.extract_session_stats("sess-005", "/home/user/myproject")
        assert stats.session_id == "sess-005"
        assert stats.input_tokens == 100


class TestFilenameFormat:
    def test_filename_format(self, tmp_path):
        """Cache filename should follow {date}--{project}--{uuid}.json."""
        entries = _basic_entries()
        _setup_project(tmp_path, "/home/user/myproject", "sess-006", entries)
        svc = _make_service(tmp_path)

        svc.extract_session_stats("sess-006", "/home/user/myproject")

        cache_files = list((tmp_path / "statistics").glob("*.json"))
        assert len(cache_files) == 1
        filename = cache_files[0].name
        # Format: {date}--{project}--{session_id}.json
        assert filename == "2026-02-15--myproject--sess-006.json"


class TestJsonlPathStored:
    def test_jsonl_path_stored(self, tmp_path):
        """CachedSessionStats.jsonl_path should point to actual JSONL."""
        entries = _basic_entries()
        proj_dir = _setup_project(tmp_path, "/home/user/myproject", "sess-007", entries)
        svc = _make_service(tmp_path)

        stats = svc.extract_session_stats("sess-007", "/home/user/myproject")

        expected_path = str(proj_dir / "sess-007.jsonl")
        assert stats.jsonl_path == expected_path


class TestDailyAggregate:
    def test_daily_aggregate(self, tmp_path):
        """Two sessions same date -> summed totals."""
        entries1 = _basic_entries(input_tokens=100, output_tokens=50)
        entries2 = _basic_entries(
            timestamp_start="2026-02-15T14:00:00.000Z",
            timestamp_end="2026-02-15T14:30:00.000Z",
            input_tokens=200,
            output_tokens=75,
        )
        _setup_project(tmp_path, "/home/user/myproject", "sess-a1", entries1)
        _setup_project(tmp_path, "/home/user/myproject", "sess-a2", entries2)
        svc = _make_service(tmp_path)

        agg = svc.get_daily_stats("2026-02-15")

        assert agg.total_sessions == 2
        assert agg.total_input_tokens == 300
        assert agg.total_output_tokens == 125
        assert agg.total_tool_calls == 2  # 1 Read per session


class TestDailyRange:
    def test_daily_range(self, tmp_path):
        """3 dates, 2-day range -> correct filter."""
        entries_14 = _basic_entries(
            timestamp_start="2026-02-14T10:00:00.000Z",
            timestamp_end="2026-02-14T10:01:00.000Z",
        )
        entries_15 = _basic_entries(
            timestamp_start="2026-02-15T10:00:00.000Z",
            timestamp_end="2026-02-15T10:01:00.000Z",
        )
        entries_16 = _basic_entries(
            timestamp_start="2026-02-16T10:00:00.000Z",
            timestamp_end="2026-02-16T10:01:00.000Z",
        )
        _setup_project(tmp_path, "/home/user/myproject", "sess-d14", entries_14)
        _setup_project(tmp_path, "/home/user/myproject", "sess-d15", entries_15)
        _setup_project(tmp_path, "/home/user/myproject", "sess-d16", entries_16)
        svc = _make_service(tmp_path)

        agg = svc.get_daily_stats("2026-02-14", date_end="2026-02-15")

        assert agg.total_sessions == 2
        assert agg.date_range == "2026-02-14 to 2026-02-15"
        session_ids = {s.session_id for s in agg.sessions}
        assert "sess-d14" in session_ids
        assert "sess-d15" in session_ids
        assert "sess-d16" not in session_ids


class TestDailyEmpty:
    def test_daily_empty(self, tmp_path):
        """No sessions for date -> empty aggregate."""
        _setup_project(tmp_path, "/home/user/myproject", "sess-e1", _basic_entries())
        svc = _make_service(tmp_path)

        agg = svc.get_daily_stats("2026-03-01")

        assert agg.total_sessions == 0
        assert agg.sessions == []
        assert agg.total_input_tokens == 0


class TestModelDistribution:
    def test_model_distribution(self, tmp_path):
        """Two different models -> correct dict."""
        entries1 = _basic_entries(model="claude-opus-4-6")
        entries2 = _basic_entries(
            timestamp_start="2026-02-15T14:00:00.000Z",
            timestamp_end="2026-02-15T14:01:00.000Z",
            model="claude-sonnet-4-5-20250929",
        )
        _setup_project(tmp_path, "/home/user/myproject", "sess-m1", entries1)
        _setup_project(tmp_path, "/home/user/myproject", "sess-m2", entries2)
        svc = _make_service(tmp_path)

        agg = svc.get_daily_stats("2026-02-15")

        assert agg.model_distribution == {
            "claude-opus-4-6": 1,
            "claude-sonnet-4-5-20250929": 1,
        }


class TestToolsHistogramMerge:
    def test_tools_histogram_merge(self, tmp_path):
        """Overlapping tool counts should be summed."""
        entries1 = [
            _user_entry("Do stuff", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [
                    _tool_use_block("Read", {"file_path": "/tmp/a.py"}),
                    _tool_use_block("Bash", {"command": "ls"}),
                ],
                timestamp="2026-02-15T10:01:00.000Z",
            ),
        ]
        entries2 = [
            _user_entry("More stuff", timestamp="2026-02-15T14:00:00.000Z"),
            _assistant_entry(
                [
                    _tool_use_block("Read", {"file_path": "/tmp/b.py"}),
                    _tool_use_block("Read", {"file_path": "/tmp/c.py"}),
                    _tool_use_block("Write", {"file_path": "/tmp/d.py"}),
                ],
                timestamp="2026-02-15T14:01:00.000Z",
            ),
        ]
        _setup_project(tmp_path, "/home/user/myproject", "sess-t1", entries1)
        _setup_project(tmp_path, "/home/user/myproject", "sess-t2", entries2)
        svc = _make_service(tmp_path)

        agg = svc.get_daily_stats("2026-02-15")

        assert agg.tools_histogram["Read"] == 3  # 1 + 2
        assert agg.tools_histogram["Bash"] == 1
        assert agg.tools_histogram["Write"] == 1


class TestExtractAndLink:
    def test_extract_and_link(self, tmp_path):
        """Multiple session IDs -> all cached."""
        entries1 = _basic_entries()
        entries2 = _basic_entries(
            timestamp_start="2026-02-15T14:00:00.000Z",
            timestamp_end="2026-02-15T14:01:00.000Z",
        )
        _setup_project(tmp_path, "/home/user/myproject", "sess-link1", entries1)
        _setup_project(tmp_path, "/home/user/myproject", "sess-link2", entries2)
        svc = _make_service(tmp_path)

        results = svc.extract_and_link(
            ["sess-link1", "sess-link2", "nonexistent"],
            project_path="/home/user/myproject",
        )

        # Should return 2 (nonexistent is skipped)
        assert len(results) == 2
        ids = {r.session_id for r in results}
        assert "sess-link1" in ids
        assert "sess-link2" in ids

        # Cache files should exist
        cache_files = list((tmp_path / "statistics").glob("*.json"))
        assert len(cache_files) == 2
