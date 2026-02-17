"""Tests for ClaudeSessionService."""

import json

import pytest

from ai_usage_log.services.claude_session_service import ClaudeSessionService


# --- Helpers to create JSONL entries ---


def _user_entry(content, timestamp="2026-02-15T10:00:00.000Z", is_meta=None, git_branch="main"):
    """Create a user-type JSONL entry."""
    entry = {
        "type": "user",
        "timestamp": timestamp,
        "gitBranch": git_branch,
        "message": {"role": "user", "content": content},
    }
    if is_meta is not None:
        entry["isMeta"] = is_meta
    return entry


def _assistant_entry(
    content_blocks,
    timestamp="2026-02-15T10:01:00.000Z",
    model="claude-opus-4-6",
    input_tokens=100,
    output_tokens=50,
    cache_read=0,
    cache_creation=0,
):
    """Create an assistant-type JSONL entry."""
    return {
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


def _text_block(text):
    return {"type": "text", "text": text}


def _tool_use_block(name, tool_input=None):
    return {"type": "tool_use", "name": name, "input": tool_input or {}}


def _tool_result_block(content="ok"):
    return {"type": "tool_result", "content": content}


def _write_jsonl(path, entries):
    """Write a list of dicts as JSONL."""
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _setup_project(tmp_path, project_path="/home/user/myproject", session_id="abc-123", entries=None):
    """Create a project directory with a JSONL session file."""
    encoded = ClaudeSessionService.encode_project_path(project_path)
    proj_dir = tmp_path / encoded
    proj_dir.mkdir(parents=True, exist_ok=True)
    if entries is not None:
        _write_jsonl(proj_dir / f"{session_id}.jsonl", entries)
    return proj_dir


# --- Path encoding tests ---


class TestEncodeProjectPath:
    def test_basic_path(self):
        assert ClaudeSessionService.encode_project_path("/home/user/project") == "-home-user-project"

    def test_dots_replaced(self):
        assert ClaudeSessionService.encode_project_path("/home/user/.claude") == "-home-user--claude"

    def test_hyphens_preserved(self):
        assert ClaudeSessionService.encode_project_path("/home/my-user/repo") == "-home-my-user-repo"

    def test_complex_path(self):
        result = ClaudeSessionService.encode_project_path("/home/sinh/git-repos/sinh-x/tools/ai-usage-log")
        assert result == "-home-sinh-git-repos-sinh-x-tools-ai-usage-log"


# --- List sessions tests ---


class TestListSessions:
    def test_empty_directory(self, tmp_path):
        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        result = svc.list_sessions()
        assert result.count == 0
        assert result.sessions == []

    def test_no_projects_dir(self, tmp_path):
        svc = ClaudeSessionService(claude_projects_dir=tmp_path / "nonexistent")
        result = svc.list_sessions()
        assert result.count == 0

    def test_list_populated(self, tmp_path):
        entries = [
            _user_entry("Hello", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry([_text_block("Hi!")], timestamp="2026-02-15T10:00:05.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-001", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        result = svc.list_sessions(project_path="/home/user/proj")

        assert result.count == 1
        info = result.sessions[0]
        assert info.session_id == "sess-001"
        assert info.start_time == "2026-02-15T10:00:00.000Z"
        assert info.message_count == 2
        assert info.git_branch == "main"

    def test_list_with_limit(self, tmp_path):
        proj_dir = _setup_project(tmp_path, "/home/user/proj")
        for i in range(5):
            entries = [_user_entry(f"msg {i}")]
            _write_jsonl(proj_dir / f"sess-{i:03d}.jsonl", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        result = svc.list_sessions(project_path="/home/user/proj", limit=3)
        assert result.count == 3

    def test_list_sorted_by_mtime(self, tmp_path):
        import time

        proj_dir = _setup_project(tmp_path, "/home/user/proj")
        _write_jsonl(proj_dir / "older.jsonl", [_user_entry("old")])
        time.sleep(0.05)
        _write_jsonl(proj_dir / "newer.jsonl", [_user_entry("new")])

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        result = svc.list_sessions(project_path="/home/user/proj")
        assert result.sessions[0].session_id == "newer"
        assert result.sessions[0].is_current is True

    def test_list_nonexistent_project(self, tmp_path):
        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        result = svc.list_sessions(project_path="/no/such/project")
        assert result.count == 0


# --- Read session / parse tests ---


class TestReadSession:
    def test_basic_parse(self, tmp_path):
        entries = [
            _user_entry("What is Python?", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_text_block("Python is a programming language.")],
                timestamp="2026-02-15T10:01:00.000Z",
                input_tokens=100,
                output_tokens=50,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-basic", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-basic", "/home/user/proj")

        assert data.session_id == "sess-basic"
        assert data.model == "claude-opus-4-6"
        assert data.start_time == "2026-02-15T10:00:00.000Z"
        assert data.end_time == "2026-02-15T10:01:00.000Z"
        assert data.duration_minutes == 1.0
        assert data.total_user_messages == 1
        assert data.total_assistant_messages == 1
        assert data.input_tokens == 100
        assert data.output_tokens == 50
        assert len(data.conversation) == 1
        assert data.conversation[0].user_prompt == "What is Python?"
        assert "Python is a programming language" in data.conversation[0].response_summary

    def test_noise_filtering(self, tmp_path):
        """Entries with skip types should be ignored."""
        entries = [
            {"type": "file-history-snapshot", "messageId": "x", "snapshot": {}},
            {"type": "progress", "data": "loading"},
            {"type": "queue-operation", "op": "enqueue"},
            {"type": "system", "info": "started"},
            _user_entry("Real message", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry([_text_block("Response")], timestamp="2026-02-15T10:01:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-noise", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-noise", "/home/user/proj")

        assert data.total_user_messages == 1
        assert data.total_assistant_messages == 1
        assert len(data.conversation) == 1

    def test_is_meta_filtering(self, tmp_path):
        """isMeta=True messages should be skipped."""
        entries = [
            _user_entry("Real question", timestamp="2026-02-15T10:00:00.000Z"),
            _user_entry("Skill injection content", timestamp="2026-02-15T10:00:01.000Z", is_meta=True),
            _assistant_entry([_text_block("Answer")], timestamp="2026-02-15T10:01:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-meta", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-meta", "/home/user/proj")

        assert data.total_user_messages == 1
        assert len(data.conversation) == 1
        assert data.conversation[0].user_prompt == "Real question"

    def test_system_tag_filtering(self, tmp_path):
        """Messages containing system tags should be filtered."""
        entries = [
            _user_entry("Real question", timestamp="2026-02-15T10:00:00.000Z"),
            _user_entry(
                "<system-reminder>You must follow these rules</system-reminder>",
                timestamp="2026-02-15T10:00:01.000Z",
            ),
            _assistant_entry([_text_block("Answer")], timestamp="2026-02-15T10:01:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-systag", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-systag", "/home/user/proj")

        assert data.total_user_messages == 1

    def test_tool_result_only_filtering(self, tmp_path):
        """User messages that are only tool_result blocks should be filtered."""
        entries = [
            _user_entry("Real question", timestamp="2026-02-15T10:00:00.000Z"),
            _user_entry(
                [_tool_result_block("allowed"), _tool_result_block("data")],
                timestamp="2026-02-15T10:00:05.000Z",
            ),
            _assistant_entry([_text_block("Answer")], timestamp="2026-02-15T10:01:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-toolres", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-toolres", "/home/user/proj")

        assert data.total_user_messages == 1

    def test_tool_tracking(self, tmp_path):
        """Tool calls should be tracked in summary and file activity."""
        entries = [
            _user_entry("Read my file", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [
                    _tool_use_block("Read", {"file_path": "/home/user/foo.py"}),
                    _tool_use_block("Edit", {"file_path": "/home/user/bar.py"}),
                    _tool_use_block("Bash", {"command": "git status"}),
                    _text_block("Done editing."),
                ],
                timestamp="2026-02-15T10:01:00.000Z",
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-tools", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-tools", "/home/user/proj")

        assert data.total_tool_calls == 3
        assert data.tools_summary == {"Read": 1, "Edit": 1, "Bash": 1}
        assert "/home/user/foo.py" in data.files_read
        assert "/home/user/bar.py" in data.files_written
        assert "git status" in data.commands_run
        assert data.conversation[0].tools_used == ["Read", "Edit", "Bash"]

    def test_duration_calculation(self, tmp_path):
        entries = [
            _user_entry("Start", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry([_text_block("Mid")], timestamp="2026-02-15T10:30:00.000Z"),
            _user_entry("End", timestamp="2026-02-15T11:00:00.000Z"),
            _assistant_entry([_text_block("Done")], timestamp="2026-02-15T11:05:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-dur", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-dur", "/home/user/proj")

        assert data.duration_minutes == 65.0

    def test_prompt_truncation(self, tmp_path):
        long_prompt = "x" * 1000
        entries = [
            _user_entry(long_prompt, timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry([_text_block("ok")], timestamp="2026-02-15T10:01:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-trunc", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-trunc", "/home/user/proj")

        assert len(data.conversation[0].user_prompt) == 500

    def test_response_truncation(self, tmp_path):
        long_response = "y" * 500
        entries = [
            _user_entry("Ask", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry([_text_block(long_response)], timestamp="2026-02-15T10:01:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-rtrunc", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-rtrunc", "/home/user/proj")

        assert len(data.conversation[0].response_summary) == 200

    def test_not_found(self, tmp_path):
        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            svc.read_session("nonexistent", "/home/user/proj")

    def test_token_accumulation(self, tmp_path):
        entries = [
            _user_entry("Q1", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_text_block("A1")],
                timestamp="2026-02-15T10:01:00.000Z",
                input_tokens=100,
                output_tokens=50,
                cache_read=200,
                cache_creation=300,
            ),
            _user_entry("Q2", timestamp="2026-02-15T10:02:00.000Z"),
            _assistant_entry(
                [_text_block("A2")],
                timestamp="2026-02-15T10:03:00.000Z",
                input_tokens=150,
                output_tokens=75,
                cache_read=100,
                cache_creation=0,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-tokens", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-tokens", "/home/user/proj")

        assert data.input_tokens == 250
        assert data.output_tokens == 125
        assert data.cache_read_tokens == 300
        assert data.cache_creation_tokens == 300
        assert data.total_tokens == 250 + 125 + 300 + 300

    def test_multiple_conversation_turns(self, tmp_path):
        entries = [
            _user_entry("First question", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry([_text_block("First answer")], timestamp="2026-02-15T10:01:00.000Z"),
            _user_entry("Second question", timestamp="2026-02-15T10:02:00.000Z"),
            _assistant_entry([_text_block("Second answer")], timestamp="2026-02-15T10:03:00.000Z"),
            _user_entry("Third question", timestamp="2026-02-15T10:04:00.000Z"),
            _assistant_entry([_text_block("Third answer")], timestamp="2026-02-15T10:05:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-multi", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-multi", "/home/user/proj")

        assert len(data.conversation) == 3
        assert data.conversation[0].user_prompt == "First question"
        assert data.conversation[1].user_prompt == "Second question"
        assert data.conversation[2].user_prompt == "Third question"

    def test_interrupted_message_filtering(self, tmp_path):
        entries = [
            _user_entry("Real question", timestamp="2026-02-15T10:00:00.000Z"),
            _user_entry(
                "[Request interrupted by user for tool use]",
                timestamp="2026-02-15T10:00:01.000Z",
            ),
            _assistant_entry([_text_block("Answer")], timestamp="2026-02-15T10:01:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-interrupt", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-interrupt", "/home/user/proj")

        assert data.total_user_messages == 1

    def test_glob_grep_path_extraction(self, tmp_path):
        """Glob and Grep use 'path' not 'file_path'."""
        entries = [
            _user_entry("Search", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [
                    _tool_use_block("Glob", {"path": "/home/user/src", "pattern": "*.py"}),
                    _tool_use_block("Grep", {"path": "/home/user/src", "pattern": "import"}),
                ],
                timestamp="2026-02-15T10:01:00.000Z",
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-paths", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-paths", "/home/user/proj")

        assert "/home/user/src" in data.files_read

    def test_find_session_across_projects(self, tmp_path):
        """When no project_path given, should scan all projects."""
        entries = [_user_entry("hello", timestamp="2026-02-15T10:00:00.000Z")]
        _setup_project(tmp_path, "/home/user/proj-a", "unique-sess", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("unique-sess")

        assert data.session_id == "unique-sess"


# --- Timezone conversion tests ---


class TestTimezoneConversion:
    def test_no_offset_passthrough(self, tmp_path):
        """With tz_offset_hours=0, timestamps stay as-is (UTC)."""
        entries = [
            _user_entry("Hello", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry([_text_block("Hi")], timestamp="2026-02-15T10:01:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-tz0", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path, tz_offset_hours=0)
        data = svc.read_session("sess-tz0", "/home/user/proj")

        assert data.start_time == "2026-02-15T10:00:00.000Z"
        assert data.end_time == "2026-02-15T10:01:00.000Z"
        assert data.conversation[0].timestamp == "2026-02-15T10:00:00.000Z"

    def test_positive_offset(self, tmp_path):
        """With tz_offset_hours=7, timestamps shift +7h."""
        entries = [
            _user_entry("Hello", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry([_text_block("Hi")], timestamp="2026-02-15T10:01:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-tz7", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path, tz_offset_hours=7)
        data = svc.read_session("sess-tz7", "/home/user/proj")

        assert data.start_time.startswith("2026-02-15T17:00:00")
        assert data.end_time.startswith("2026-02-15T17:01:00")
        assert data.conversation[0].timestamp.startswith("2026-02-15T17:00:00")
        assert "+0700" in data.start_time

    def test_negative_offset(self, tmp_path):
        """With tz_offset_hours=-5 (EST), timestamps shift -5h."""
        entries = [
            _user_entry("Hello", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry([_text_block("Hi")], timestamp="2026-02-15T10:01:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-tz-5", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path, tz_offset_hours=-5)
        data = svc.read_session("sess-tz-5", "/home/user/proj")

        assert data.start_time.startswith("2026-02-15T05:00:00")
        assert "-0500" in data.start_time

    def test_offset_date_rollover(self, tmp_path):
        """Offset that crosses midnight should change the date."""
        entries = [
            _user_entry("Hello", timestamp="2026-02-15T23:00:00.000Z"),
            _assistant_entry([_text_block("Hi")], timestamp="2026-02-15T23:30:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-tz-roll", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path, tz_offset_hours=7)
        data = svc.read_session("sess-tz-roll", "/home/user/proj")

        assert data.start_time.startswith("2026-02-16T06:00:00")

    def test_duration_unaffected_by_offset(self, tmp_path):
        """Duration should be the same regardless of timezone offset."""
        entries = [
            _user_entry("Start", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry([_text_block("Done")], timestamp="2026-02-15T11:05:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-tz-dur", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path, tz_offset_hours=7)
        data = svc.read_session("sess-tz-dur", "/home/user/proj")

        assert data.duration_minutes == 65.0

    def test_list_sessions_with_offset(self, tmp_path):
        """list_sessions should also convert timestamps."""
        entries = [
            _user_entry("Hello", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry([_text_block("Hi")], timestamp="2026-02-15T10:01:00.000Z"),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-list-tz", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path, tz_offset_hours=7)
        result = svc.list_sessions(project_path="/home/user/proj")

        assert result.sessions[0].start_time is not None
        assert result.sessions[0].start_time.startswith("2026-02-15T17:00:00")
