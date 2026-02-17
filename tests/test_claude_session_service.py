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
    message_id=None,
):
    """Create an assistant-type JSONL entry."""
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


def _progress_entry(
    tool_use_id,
    input_tokens=0,
    output_tokens=0,
    cache_creation=0,
    message_id="sub_msg_001",
    data_type="agent_progress",
    msg_type="assistant",
):
    """Create a progress-type JSONL entry for sub-agent tokens."""
    return {
        "type": "progress",
        "toolUseID": tool_use_id,
        "data": {
            "type": data_type,
            "message": {
                "type": msg_type,
                "message": {
                    "id": message_id,
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cache_creation_input_tokens": cache_creation,
                    },
                },
            },
        },
    }


def _text_block(text):
    return {"type": "text", "text": text}


def _tool_use_block(name, tool_input=None, tool_use_id=None):
    block = {"type": "tool_use", "name": name, "input": tool_input or {}}
    if tool_use_id:
        block["id"] = tool_use_id
    return block


def _tool_result_block(content="ok", tool_use_id=None, is_error=None):
    block = {"type": "tool_result", "content": content}
    if tool_use_id:
        block["tool_use_id"] = tool_use_id
    if is_error is not None:
        block["is_error"] = is_error
    return block


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
        # total_tokens excludes cache_read (misleading when summed across turns)
        assert data.total_tokens == 250 + 125 + 300

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


# --- Per-turn token tests ---


class TestPerTurnTokens:
    def test_single_turn_tokens(self, tmp_path):
        """Each turn should have its own token breakdown."""
        entries = [
            _user_entry("Hello", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_text_block("Hi there")],
                timestamp="2026-02-15T10:01:00.000Z",
                input_tokens=100,
                output_tokens=50,
                cache_read=200,
                cache_creation=300,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-turn-tok", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-turn-tok", "/home/user/proj")

        assert len(data.conversation) == 1
        tokens = data.conversation[0].tokens
        assert tokens is not None
        assert tokens.input_tokens == 100
        assert tokens.output_tokens == 50
        assert tokens.cache_read_tokens == 200
        assert tokens.cache_creation_tokens == 300
        assert tokens.total == 650

    def test_multi_turn_tokens_independent(self, tmp_path):
        """Each turn accumulates only its own assistant entries' tokens."""
        entries = [
            _user_entry("Q1", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_text_block("A1")],
                timestamp="2026-02-15T10:01:00.000Z",
                input_tokens=100,
                output_tokens=50,
                cache_read=0,
                cache_creation=0,
            ),
            _user_entry("Q2", timestamp="2026-02-15T10:02:00.000Z"),
            _assistant_entry(
                [_text_block("A2")],
                timestamp="2026-02-15T10:03:00.000Z",
                input_tokens=200,
                output_tokens=75,
                cache_read=100,
                cache_creation=50,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-multi-tok", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-multi-tok", "/home/user/proj")

        assert len(data.conversation) == 2

        t1 = data.conversation[0].tokens
        assert t1.input_tokens == 100
        assert t1.output_tokens == 50
        assert t1.cache_read_tokens == 0
        assert t1.cache_creation_tokens == 0
        assert t1.total == 150

        t2 = data.conversation[1].tokens
        assert t2.input_tokens == 200
        assert t2.output_tokens == 75
        assert t2.cache_read_tokens == 100
        assert t2.cache_creation_tokens == 50
        assert t2.total == 425

    def test_multiple_assistant_entries_per_turn(self, tmp_path):
        """Multiple assistant entries within a single turn should sum tokens."""
        entries = [
            _user_entry("Do something complex", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_tool_use_block("Read", {"file_path": "/tmp/a.py"})],
                timestamp="2026-02-15T10:01:00.000Z",
                input_tokens=100,
                output_tokens=30,
            ),
            # Tool result comes back as user entry (tool_result only — filtered)
            _user_entry(
                [_tool_result_block("file contents")],
                timestamp="2026-02-15T10:01:05.000Z",
            ),
            _assistant_entry(
                [_text_block("Here's what I found")],
                timestamp="2026-02-15T10:01:10.000Z",
                input_tokens=150,
                output_tokens=60,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-multi-asst", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-multi-asst", "/home/user/proj")

        # Should be a single turn (tool_result user entry doesn't start new turn)
        assert len(data.conversation) == 1
        tokens = data.conversation[0].tokens
        assert tokens.input_tokens == 250  # 100 + 150
        assert tokens.output_tokens == 90  # 30 + 60

    def test_turn_tokens_sum_equals_session_total(self, tmp_path):
        """Sum of per-turn tokens should equal session-level totals."""
        entries = [
            _user_entry("Q1", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_text_block("A1")],
                timestamp="2026-02-15T10:01:00.000Z",
                input_tokens=100,
                output_tokens=50,
                cache_read=10,
                cache_creation=20,
            ),
            _user_entry("Q2", timestamp="2026-02-15T10:02:00.000Z"),
            _assistant_entry(
                [_text_block("A2")],
                timestamp="2026-02-15T10:03:00.000Z",
                input_tokens=200,
                output_tokens=75,
                cache_read=30,
                cache_creation=40,
            ),
            _user_entry("Q3", timestamp="2026-02-15T10:04:00.000Z"),
            _assistant_entry(
                [_text_block("A3")],
                timestamp="2026-02-15T10:05:00.000Z",
                input_tokens=300,
                output_tokens=100,
                cache_read=50,
                cache_creation=60,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-tok-sum", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-tok-sum", "/home/user/proj")

        turn_input = sum(t.tokens.input_tokens for t in data.conversation)
        turn_output = sum(t.tokens.output_tokens for t in data.conversation)
        turn_cache_r = sum(t.tokens.cache_read_tokens for t in data.conversation)
        turn_cache_c = sum(t.tokens.cache_creation_tokens for t in data.conversation)

        assert turn_input == data.input_tokens
        assert turn_output == data.output_tokens
        assert turn_cache_r == data.cache_read_tokens
        assert turn_cache_c == data.cache_creation_tokens

    def test_orphan_tokens_before_first_user_message(self, tmp_path):
        """Assistant entries before first user message should not lose tokens.

        Regression test for #4: when assistant entries precede the first real
        user message, their tokens were added to session totals but not to any
        ConversationTurn.tokens, breaking the sum invariant.
        """
        entries = [
            # Assistant entries before any user message (orphan tokens)
            _assistant_entry(
                [_text_block("System init response")],
                timestamp="2026-02-15T10:00:00.000Z",
                input_tokens=50,
                output_tokens=20,
                cache_read=500,
                cache_creation=1000,
            ),
            _assistant_entry(
                [_text_block("Another pre-user response")],
                timestamp="2026-02-15T10:00:05.000Z",
                input_tokens=30,
                output_tokens=10,
                cache_read=300,
                cache_creation=200,
            ),
            # First real user message
            _user_entry("Hello!", timestamp="2026-02-15T10:01:00.000Z"),
            _assistant_entry(
                [_text_block("Hi there!")],
                timestamp="2026-02-15T10:01:05.000Z",
                input_tokens=100,
                output_tokens=50,
                cache_read=200,
                cache_creation=0,
            ),
            # Second turn
            _user_entry("What's up?", timestamp="2026-02-15T10:02:00.000Z"),
            _assistant_entry(
                [_text_block("Not much!")],
                timestamp="2026-02-15T10:02:05.000Z",
                input_tokens=120,
                output_tokens=60,
                cache_read=100,
                cache_creation=0,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-orphan", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-orphan", "/home/user/proj")

        # Session totals include ALL assistant entries
        assert data.input_tokens == 300   # 50+30+100+120
        assert data.output_tokens == 140  # 20+10+50+60
        assert data.cache_read_tokens == 1100   # 500+300+200+100
        assert data.cache_creation_tokens == 1200  # 1000+200+0+0

        # Per-turn sums MUST match session totals (orphan tokens drained into first turn)
        turn_input = sum(t.tokens.input_tokens for t in data.conversation)
        turn_output = sum(t.tokens.output_tokens for t in data.conversation)
        turn_cache_r = sum(t.tokens.cache_read_tokens for t in data.conversation)
        turn_cache_c = sum(t.tokens.cache_creation_tokens for t in data.conversation)

        assert turn_input == data.input_tokens
        assert turn_output == data.output_tokens
        assert turn_cache_r == data.cache_read_tokens
        assert turn_cache_c == data.cache_creation_tokens

        # First turn should contain orphan tokens + its own tokens
        t1 = data.conversation[0].tokens
        assert t1.input_tokens == 180   # 50+30 (orphan) + 100 (own)
        assert t1.output_tokens == 80   # 20+10 (orphan) + 50 (own)

        # Second turn should have only its own tokens
        t2 = data.conversation[1].tokens
        assert t2.input_tokens == 120
        assert t2.output_tokens == 60

    def test_all_orphan_no_user_messages(self, tmp_path):
        """Session with only assistant entries and no user messages.

        Edge case: all tokens are orphaned, no turns exist to drain into.
        Session totals should still be correct; conversation should be empty.
        """
        entries = [
            _assistant_entry(
                [_text_block("Init")],
                timestamp="2026-02-15T10:00:00.000Z",
                input_tokens=100,
                output_tokens=50,
                cache_read=500,
                cache_creation=200,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-no-user", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-no-user", "/home/user/proj")

        # Session totals still correct
        assert data.input_tokens == 100
        assert data.output_tokens == 50
        # total_tokens = input + output + cache_creation (excludes cache_read)
        assert data.total_tokens == 100 + 50 + 200

        # No turns to attribute tokens to
        assert len(data.conversation) == 0

    def test_context_window_single_assistant_per_turn(self, tmp_path):
        """context_window should be the input-side tokens of the last API call."""
        entries = [
            _user_entry("Q1", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_text_block("A1")],
                timestamp="2026-02-15T10:01:00.000Z",
                input_tokens=10,
                output_tokens=50,
                cache_read=25000,
                cache_creation=3000,
            ),
            _user_entry("Q2", timestamp="2026-02-15T10:02:00.000Z"),
            _assistant_entry(
                [_text_block("A2")],
                timestamp="2026-02-15T10:03:00.000Z",
                input_tokens=10,
                output_tokens=75,
                cache_read=28000,
                cache_creation=500,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-cw-basic", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-cw-basic", "/home/user/proj")

        # context_window = input + cache_read + cache_creation (no output)
        assert data.conversation[0].context_window == 10 + 25000 + 3000  # 28010
        assert data.conversation[1].context_window == 10 + 28000 + 500   # 28510
        # Context should grow between turns
        assert data.conversation[1].context_window > data.conversation[0].context_window

    def test_context_window_multiple_api_calls_per_turn(self, tmp_path):
        """With multiple assistant entries per turn, context_window = last call's input-side."""
        entries = [
            _user_entry("Do something", timestamp="2026-02-15T10:00:00.000Z"),
            # First API call (tool use)
            _assistant_entry(
                [_tool_use_block("Read", {"file_path": "/tmp/a.py"})],
                timestamp="2026-02-15T10:01:00.000Z",
                input_tokens=5,
                output_tokens=10,
                cache_read=50000,
                cache_creation=2000,
            ),
            # Tool result (filtered as tool_result-only)
            _user_entry(
                [_tool_result_block("file contents")],
                timestamp="2026-02-15T10:01:05.000Z",
            ),
            # Second API call (with tool result in context — larger)
            _assistant_entry(
                [_text_block("Here's the file")],
                timestamp="2026-02-15T10:01:10.000Z",
                input_tokens=5,
                output_tokens=30,
                cache_read=52000,
                cache_creation=800,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-cw-multi", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-cw-multi", "/home/user/proj")

        assert len(data.conversation) == 1
        # Should be the LAST API call's input-side, not the first
        assert data.conversation[0].context_window == 5 + 52000 + 800  # 52805
        # NOT 5 + 50000 + 2000 = 52005 (first call)


# --- Streamed chunk dedup tests ---


class TestStreamedChunkDedup:
    def test_streamed_chunks_dedup(self, tmp_path):
        """Same message.id, multiple entries → counted once (last chunk wins)."""
        entries = [
            _user_entry("Hello", timestamp="2026-02-15T10:00:00.000Z"),
            # Streamed chunk 1: partial output
            _assistant_entry(
                [_text_block("Hel")],
                timestamp="2026-02-15T10:01:00.000Z",
                message_id="msg_abc",
                input_tokens=100,
                output_tokens=10,
                cache_read=500,
                cache_creation=200,
            ),
            # Streamed chunk 2: cumulative output
            _assistant_entry(
                [_text_block("Hello there")],
                timestamp="2026-02-15T10:01:01.000Z",
                message_id="msg_abc",
                input_tokens=100,
                output_tokens=30,
                cache_read=500,
                cache_creation=200,
            ),
            # Streamed chunk 3: final cumulative
            _assistant_entry(
                [_text_block("Hello there, how are you?")],
                timestamp="2026-02-15T10:01:02.000Z",
                message_id="msg_abc",
                input_tokens=100,
                output_tokens=50,
                cache_read=500,
                cache_creation=200,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-dedup", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-dedup", "/home/user/proj")

        # Should count as one API response, not 3x
        assert data.input_tokens == 100  # not 300
        assert data.output_tokens == 50  # not 90 (10+30+50)
        assert data.cache_read_tokens == 500  # not 1500
        assert data.cache_creation_tokens == 200  # not 600

    def test_different_message_ids_not_deduped(self, tmp_path):
        """Different message.id entries should each be counted."""
        entries = [
            _user_entry("Hello", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_text_block("First response")],
                timestamp="2026-02-15T10:01:00.000Z",
                message_id="msg_001",
                input_tokens=100,
                output_tokens=50,
            ),
            # Tool result
            _user_entry(
                [_tool_result_block("data")],
                timestamp="2026-02-15T10:01:05.000Z",
            ),
            _assistant_entry(
                [_text_block("Second response")],
                timestamp="2026-02-15T10:01:10.000Z",
                message_id="msg_002",
                input_tokens=200,
                output_tokens=75,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-no-dedup", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-no-dedup", "/home/user/proj")

        assert data.input_tokens == 300  # 100 + 200
        assert data.output_tokens == 125  # 50 + 75


# --- Sub-agent token tests ---


class TestSubagentTokens:
    def test_subagent_tokens_from_progress(self, tmp_path):
        """agent_progress entries should accumulate subagent tokens."""
        entries = [
            _user_entry("Do complex task", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_tool_use_block("Task", {"prompt": "research"}, tool_use_id="toolu_task1")],
                timestamp="2026-02-15T10:01:00.000Z",
                message_id="msg_main",
                input_tokens=100,
                output_tokens=50,
            ),
            # Sub-agent progress
            _progress_entry(
                tool_use_id="toolu_task1",
                input_tokens=500,
                output_tokens=200,
                cache_creation=100,
                message_id="sub_msg_001",
            ),
            _progress_entry(
                tool_use_id="toolu_task1",
                input_tokens=800,
                output_tokens=300,
                cache_creation=50,
                message_id="sub_msg_002",
            ),
            # Tool result
            _user_entry(
                [_tool_result_block("task done")],
                timestamp="2026-02-15T10:02:00.000Z",
            ),
            _assistant_entry(
                [_text_block("Task complete")],
                timestamp="2026-02-15T10:02:05.000Z",
                message_id="msg_main2",
                input_tokens=150,
                output_tokens=60,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-subagent", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-subagent", "/home/user/proj")

        # Session-level sub-agent tokens
        assert data.subagent_input_tokens == 1300  # 500 + 800
        assert data.subagent_output_tokens == 500  # 200 + 300
        assert data.subagent_cache_creation_tokens == 150  # 100 + 50

        # Main tokens should NOT include sub-agent tokens
        assert data.input_tokens == 250  # 100 + 150
        assert data.output_tokens == 110  # 50 + 60

    def test_subagent_streamed_chunks_dedup(self, tmp_path):
        """Sub-agent progress with same message.id should be deduped."""
        entries = [
            _user_entry("Do task", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_tool_use_block("Task", {}, tool_use_id="toolu_t1")],
                timestamp="2026-02-15T10:01:00.000Z",
                message_id="msg_m1",
                input_tokens=100,
                output_tokens=50,
            ),
            # Streamed sub-agent chunks (same message_id)
            _progress_entry(
                tool_use_id="toolu_t1",
                input_tokens=500,
                output_tokens=100,
                message_id="sub_msg_same",
            ),
            _progress_entry(
                tool_use_id="toolu_t1",
                input_tokens=500,
                output_tokens=250,
                message_id="sub_msg_same",
            ),
            _user_entry(
                [_tool_result_block("done")],
                timestamp="2026-02-15T10:02:00.000Z",
            ),
            _assistant_entry(
                [_text_block("Done")],
                timestamp="2026-02-15T10:02:05.000Z",
                message_id="msg_m2",
                input_tokens=120,
                output_tokens=40,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-sub-dedup", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-sub-dedup", "/home/user/proj")

        # Should take the last chunk's values (500 input, 250 output)
        assert data.subagent_input_tokens == 500
        assert data.subagent_output_tokens == 250

    def test_non_agent_progress_ignored(self, tmp_path):
        """Progress entries that are not agent_progress should be ignored."""
        entries = [
            _user_entry("Hello", timestamp="2026-02-15T10:00:00.000Z"),
            {"type": "progress", "data": "loading"},
            {"type": "progress", "data": {"type": "other_progress"}},
            _assistant_entry(
                [_text_block("Hi")],
                timestamp="2026-02-15T10:01:00.000Z",
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-prog-skip", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-prog-skip", "/home/user/proj")

        assert data.subagent_input_tokens == 0
        assert data.subagent_output_tokens == 0


# --- Per-turn commands tests ---


class TestPerTurnCommands:
    def test_commands_tracked_per_turn(self, tmp_path):
        """Bash tool_use + tool_result → TurnCommand with status."""
        entries = [
            _user_entry("Run git status", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_tool_use_block("Bash", {"command": "git status"}, tool_use_id="toolu_bash1")],
                timestamp="2026-02-15T10:01:00.000Z",
            ),
            _user_entry(
                [_tool_result_block("On branch main", tool_use_id="toolu_bash1")],
                timestamp="2026-02-15T10:01:05.000Z",
            ),
            _assistant_entry(
                [_text_block("You're on main branch")],
                timestamp="2026-02-15T10:01:10.000Z",
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-cmd", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-cmd", "/home/user/proj")

        assert len(data.conversation) == 1
        cmds = data.conversation[0].commands
        assert len(cmds) == 1
        assert cmds[0].command == "git status"
        assert cmds[0].status == "success"

    def test_command_error_status(self, tmp_path):
        """tool_result with is_error=True → status 'error'."""
        entries = [
            _user_entry("Try something", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_tool_use_block("Bash", {"command": "exit 1"}, tool_use_id="toolu_fail")],
                timestamp="2026-02-15T10:01:00.000Z",
            ),
            _user_entry(
                [_tool_result_block("command failed", tool_use_id="toolu_fail", is_error=True)],
                timestamp="2026-02-15T10:01:05.000Z",
            ),
            _assistant_entry(
                [_text_block("That failed")],
                timestamp="2026-02-15T10:01:10.000Z",
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-cmd-err", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-cmd-err", "/home/user/proj")

        cmds = data.conversation[0].commands
        assert len(cmds) == 1
        assert cmds[0].command == "exit 1"
        assert cmds[0].status == "error"

    def test_command_without_tool_result_defaults_success(self, tmp_path):
        """Commands not resolved via tool_result default to 'success' on flush."""
        entries = [
            _user_entry("Run command", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_tool_use_block("Bash", {"command": "echo hello"}, tool_use_id="toolu_unresolved")],
                timestamp="2026-02-15T10:01:00.000Z",
            ),
            # No tool_result follows; next user message triggers flush
            _user_entry("Next question", timestamp="2026-02-15T10:02:00.000Z"),
            _assistant_entry(
                [_text_block("OK")],
                timestamp="2026-02-15T10:02:05.000Z",
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-cmd-pend", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-cmd-pend", "/home/user/proj")

        assert len(data.conversation) == 2
        cmds = data.conversation[0].commands
        assert len(cmds) == 1
        assert cmds[0].status == "success"

    def test_command_truncation(self, tmp_path):
        """Long commands should be truncated to 200 chars."""
        long_cmd = "a" * 500
        entries = [
            _user_entry("Run long cmd", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_tool_use_block("Bash", {"command": long_cmd}, tool_use_id="toolu_long")],
                timestamp="2026-02-15T10:01:00.000Z",
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-cmd-trunc", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-cmd-trunc", "/home/user/proj")

        cmds = data.conversation[0].commands
        assert len(cmds) == 1
        assert len(cmds[0].command) == 200


# --- Per-turn files modified tests ---


class TestPerTurnFilesModified:
    def test_files_modified_per_turn(self, tmp_path):
        """Write/Edit tool_use → files_modified on the turn."""
        entries = [
            _user_entry("Edit files", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [
                    _tool_use_block("Write", {"file_path": "/home/user/new.py"}),
                    _tool_use_block("Edit", {"file_path": "/home/user/old.py"}),
                ],
                timestamp="2026-02-15T10:01:00.000Z",
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-files", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-files", "/home/user/proj")

        assert len(data.conversation) == 1
        assert "/home/user/new.py" in data.conversation[0].files_modified
        assert "/home/user/old.py" in data.conversation[0].files_modified

    def test_read_not_in_files_modified(self, tmp_path):
        """Read tool should not appear in files_modified (only in files_read)."""
        entries = [
            _user_entry("Read file", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_tool_use_block("Read", {"file_path": "/home/user/readme.md"})],
                timestamp="2026-02-15T10:01:00.000Z",
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-read-only", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-read-only", "/home/user/proj")

        assert data.conversation[0].files_modified == []
        assert "/home/user/readme.md" in data.files_read


# --- to_summary tests ---


class TestToSummary:
    def test_session_data_to_summary(self, tmp_path):
        """to_summary() should produce a ClaudeSessionSummary with subset of fields."""
        entries = [
            _user_entry("Hello", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [
                    _tool_use_block("Read", {"file_path": "/tmp/a.py"}),
                    _text_block("Done"),
                ],
                timestamp="2026-02-15T10:01:00.000Z",
                input_tokens=100,
                output_tokens=50,
                cache_read=500,
                cache_creation=200,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-summary", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-summary", "/home/user/proj")
        summary = data.to_summary()

        assert summary.session_id == data.session_id
        assert summary.project_name == data.project_name
        assert summary.input_tokens == data.input_tokens
        assert summary.output_tokens == data.output_tokens
        assert summary.cache_creation_tokens == data.cache_creation_tokens
        assert summary.tools_summary == data.tools_summary
        assert len(summary.conversation) == len(data.conversation)
        # Summary should NOT have files_read, files_written, commands_run, cache_read_tokens
        assert not hasattr(summary, "files_read")
        assert not hasattr(summary, "files_written")
        assert not hasattr(summary, "commands_run")
        assert not hasattr(summary, "cache_read_tokens")


# --- total_tokens formula tests ---


class TestTotalTokensFormula:
    def test_total_tokens_excludes_cache_read(self, tmp_path):
        """total_tokens = input + output + cache_creation (no cache_read)."""
        entries = [
            _user_entry("Q1", timestamp="2026-02-15T10:00:00.000Z"),
            _assistant_entry(
                [_text_block("A1")],
                timestamp="2026-02-15T10:01:00.000Z",
                input_tokens=100,
                output_tokens=50,
                cache_read=10000,
                cache_creation=200,
            ),
        ]
        _setup_project(tmp_path, "/home/user/proj", "sess-total", entries)

        svc = ClaudeSessionService(claude_projects_dir=tmp_path)
        data = svc.read_session("sess-total", "/home/user/proj")

        assert data.total_tokens == 100 + 50 + 200  # 350, not 10350
        assert data.cache_read_tokens == 10000  # still tracked separately
