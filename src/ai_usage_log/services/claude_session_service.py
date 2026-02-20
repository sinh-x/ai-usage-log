"""Service for reading and parsing Claude Code JSONL session files."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..models.schemas import (
    ClaudeSessionData,
    ClaudeSessionInfo,
    ClaudeSessionList,
    ConversationTurn,
    TurnCommand,
    TurnTokens,
)

# Entry types to skip entirely
_SKIP_TYPES = frozenset({"file-history-snapshot", "queue-operation", "system"})

_MAX_COMMAND_LEN = 200

# Patterns in user content that indicate non-real messages
_SYSTEM_TAG_PATTERN = re.compile(
    r"<(system-reminder|local-command-caveat|local-command-stdout|command-name)"
)
_INTERRUPTED_TEXT = "[Request interrupted by user for tool use]"

# Max lengths for truncated fields
_MAX_PROMPT_LEN = 500
_MAX_RESPONSE_LEN = 200


@dataclass
class _TurnAccumulator:
    """Accumulates data for a single conversation turn."""
    timestamp: str = ""
    user_prompt: str = ""
    tools_used: list[str] = field(default_factory=list)
    response_texts: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    context_window: int = 0  # last API call's input-side tokens
    subagent_input_tokens: int = 0
    subagent_output_tokens: int = 0
    subagent_cache_creation_tokens: int = 0
    pending_commands: dict[str, str] = field(default_factory=dict)  # tool_use.id → command
    resolved_commands: list[tuple[str, str]] = field(default_factory=list)  # (command, status)
    files_modified: list[str] = field(default_factory=list)


@dataclass
class _ParseState:
    """Single-pass accumulation state for JSONL parsing."""
    model: str | None = None
    git_branch: str | None = None
    start_time: str = ""
    end_time: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    total_user_messages: int = 0
    total_assistant_messages: int = 0
    total_tool_calls: int = 0
    tools_summary: dict[str, int] = field(default_factory=dict)
    files_read: set[str] = field(default_factory=set)
    files_written: set[str] = field(default_factory=set)
    commands_run: list[str] = field(default_factory=list)
    turns: list[ConversationTurn] = field(default_factory=list)
    current_turn: _TurnAccumulator | None = None
    # Tokens from assistant entries before first user message (orphan tokens)
    orphan_input_tokens: int = 0
    orphan_output_tokens: int = 0
    orphan_cache_read_tokens: int = 0
    orphan_cache_creation_tokens: int = 0
    orphan_drained: bool = False
    # Streamed chunk dedup: message.id → last usage values seen
    seen_msg_ids: dict[str, dict] = field(default_factory=dict)
    # Sub-agent tokens (session-level)
    subagent_input_tokens: int = 0
    subagent_output_tokens: int = 0
    subagent_cache_creation_tokens: int = 0
    seen_subagent_msg_ids: dict[str, dict] = field(default_factory=dict)
    # Maps task tool_use_id → turn index for attributing sub-agent tokens
    task_tool_use_ids: dict[str, int] = field(default_factory=dict)


class ClaudeSessionService:
    """Reads and parses Claude Code JSONL session files from ~/.claude/projects/."""

    def __init__(self, claude_projects_dir: Path | None = None, tz_offset_hours: int = 0) -> None:
        if claude_projects_dir is None:
            self.claude_projects_dir = Path.home() / ".claude" / "projects"
        else:
            self.claude_projects_dir = claude_projects_dir
        self._tz = timezone(timedelta(hours=tz_offset_hours)) if tz_offset_hours else None

    def _to_local(self, ts: str) -> str:
        """Convert an RFC3339 UTC timestamp to local timezone. Pass-through if no offset configured."""
        if not self._tz or not ts:
            return ts
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            local = dt.astimezone(self._tz)
            return local.strftime("%Y-%m-%dT%H:%M:%S.") + f"{local.microsecond // 1000:03d}" + local.strftime("%z")
        except (ValueError, TypeError):
            return ts

    @staticmethod
    def encode_project_path(path: str) -> str:
        """Encode a project path the way Claude Code does: replace / and . with -."""
        return path.replace("/", "-").replace(".", "-")

    def _get_project_dir(self, project_path: str) -> Path | None:
        """Find the project directory, either by encoded path or scanning."""
        if project_path:
            encoded = self.encode_project_path(project_path)
            candidate = self.claude_projects_dir / encoded
            if candidate.is_dir():
                return candidate
            return None

        # No project path given — cannot determine which project
        return None

    def _decode_project_name(self, encoded: str) -> str:
        """Extract a human-friendly project name from the encoded directory name."""
        # The encoded path looks like "-home-sinh-git-repos-myproject"
        # Take the last segment as the project name
        parts = encoded.strip("-").split("-")
        return parts[-1] if parts else encoded

    def list_sessions(self, project_path: str = "", limit: int = 20) -> ClaudeSessionList:
        """Discover Claude Code JSONL sessions.

        If project_path is given, only scan that project's directory.
        Otherwise, scan all project directories.
        """
        sessions: list[ClaudeSessionInfo] = []
        dirs_to_scan: list[tuple[Path, str]] = []  # (dir_path, encoded_name)

        if project_path:
            proj_dir = self._get_project_dir(project_path)
            if proj_dir is None:
                return ClaudeSessionList(sessions=[], count=0)
            dirs_to_scan.append((proj_dir, proj_dir.name))
        else:
            if not self.claude_projects_dir.is_dir():
                return ClaudeSessionList(sessions=[], count=0)
            for d in sorted(self.claude_projects_dir.iterdir(), reverse=True):
                if d.is_dir():
                    dirs_to_scan.append((d, d.name))

        # Check which session is currently active (most recent .jsonl by mtime)
        current_session_id: str | None = None

        for proj_dir, encoded_name in dirs_to_scan:
            jsonl_files = sorted(
                proj_dir.glob("*.jsonl"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )

            if not current_session_id and jsonl_files:
                current_session_id = jsonl_files[0].stem

            project_name = self._decode_project_name(encoded_name)
            proj_path = project_path or encoded_name

            for jf in jsonl_files:
                if len(sessions) >= limit:
                    break

                session_id = jf.stem
                info = self._quick_scan(jf, session_id, proj_path, project_name)
                info.is_current = session_id == current_session_id
                sessions.append(info)

            if len(sessions) >= limit:
                break

        return ClaudeSessionList(sessions=sessions, count=len(sessions))

    def _quick_scan(
        self, path: Path, session_id: str, project_path: str, project_name: str
    ) -> ClaudeSessionInfo:
        """Quick-scan a JSONL file for metadata without full parsing."""
        start_time: str | None = None
        git_branch: str | None = None
        message_count = 0

        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type")
                if entry_type in _SKIP_TYPES:
                    continue

                if entry_type in ("user", "assistant"):
                    message_count += 1
                    ts = entry.get("timestamp")
                    if ts and not start_time:
                        start_time = self._to_local(ts)
                    if not git_branch:
                        git_branch = entry.get("gitBranch")

        return ClaudeSessionInfo(
            session_id=session_id,
            project_path=project_path,
            project_name=project_name,
            start_time=start_time,
            message_count=message_count,
            git_branch=git_branch,
            is_current=False,
        )

    def find_session_file(self, session_id: str, project_path: str = "") -> Path | None:
        """Find a JSONL session file by ID (public wrapper)."""
        return self._find_session_file(session_id, project_path)

    def read_session(self, session_id: str, project_path: str = "") -> ClaudeSessionData:
        """Parse a full JSONL session and return structured data."""
        jsonl_path = self._find_session_file(session_id, project_path)
        if jsonl_path is None:
            raise FileNotFoundError(f"No JSONL session found: {session_id}")

        state = _ParseState()
        encoded_name = jsonl_path.parent.name
        project_name = self._decode_project_name(encoded_name)

        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._process_entry(entry, state)

        # Flush the last turn
        self._flush_turn(state)

        # Compute duration
        duration = 0.0
        if state.start_time and state.end_time:
            try:
                t0 = datetime.fromisoformat(state.start_time.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(state.end_time.replace("Z", "+00:00"))
                duration = (t1 - t0).total_seconds() / 60.0
            except (ValueError, TypeError):
                pass

        # total_tokens excludes cache_read (misleading when summed across turns)
        total_tokens = (
            state.input_tokens
            + state.output_tokens
            + state.cache_creation_tokens
        )

        return ClaudeSessionData(
            session_id=session_id,
            project_path=project_path or encoded_name,
            project_name=project_name,
            git_branch=state.git_branch,
            model=state.model,
            start_time=state.start_time,
            end_time=state.end_time,
            duration_minutes=round(duration, 1),
            conversation=state.turns,
            total_user_messages=state.total_user_messages,
            total_assistant_messages=state.total_assistant_messages,
            total_tool_calls=state.total_tool_calls,
            total_tokens=total_tokens,
            input_tokens=state.input_tokens,
            output_tokens=state.output_tokens,
            cache_read_tokens=state.cache_read_tokens,
            cache_creation_tokens=state.cache_creation_tokens,
            subagent_input_tokens=state.subagent_input_tokens,
            subagent_output_tokens=state.subagent_output_tokens,
            subagent_cache_creation_tokens=state.subagent_cache_creation_tokens,
            tools_summary=dict(state.tools_summary),
            files_read=sorted(state.files_read),
            files_written=sorted(state.files_written),
            commands_run=state.commands_run,
        )

    def _find_session_file(self, session_id: str, project_path: str) -> Path | None:
        """Find a JSONL session file by ID."""
        if project_path:
            proj_dir = self._get_project_dir(project_path)
            if proj_dir:
                candidate = proj_dir / f"{session_id}.jsonl"
                if candidate.is_file():
                    return candidate
            return None

        # Scan all project directories
        if not self.claude_projects_dir.is_dir():
            return None
        for d in self.claude_projects_dir.iterdir():
            if d.is_dir():
                candidate = d / f"{session_id}.jsonl"
                if candidate.is_file():
                    return candidate
        return None

    def _process_entry(self, entry: dict, state: _ParseState) -> None:
        """Process a single JSONL entry, updating state."""
        entry_type = entry.get("type")
        if entry_type in _SKIP_TYPES:
            return

        timestamp = entry.get("timestamp", "")
        if timestamp:
            local_ts = self._to_local(timestamp)
            if not state.start_time:
                state.start_time = local_ts
            state.end_time = local_ts

        if not state.git_branch:
            state.git_branch = entry.get("gitBranch")

        if entry_type == "user":
            self._process_user_entry(entry, state)
        elif entry_type == "assistant":
            self._process_assistant_entry(entry, state)
        elif entry_type == "progress":
            self._process_progress_entry(entry, state)

    def _process_user_entry(self, entry: dict, state: _ParseState) -> None:
        """Process a user-type JSONL entry."""
        is_meta = entry.get("isMeta")
        if is_meta:
            return

        message = entry.get("message", {})
        if not isinstance(message, dict):
            return

        content = message.get("content", "")

        # String content = real user message
        if isinstance(content, str) and content.strip():
            # Filter out system-tag injections
            if _SYSTEM_TAG_PATTERN.search(content):
                return
            if content.strip() == _INTERRUPTED_TEXT:
                return

            state.total_user_messages += 1

            # Flush previous turn, start new one
            self._flush_turn(state)
            state.current_turn = _TurnAccumulator(
                timestamp=self._to_local(entry.get("timestamp", "")),
                user_prompt=content[:_MAX_PROMPT_LEN],
            )
            return

        # List content — check if it's tool_result only (approval responses)
        if isinstance(content, list):
            types = {block.get("type") for block in content if isinstance(block, dict)}
            if types == {"tool_result"}:
                # Resolve pending commands from tool results
                if state.current_turn:
                    for block in content:
                        if not isinstance(block, dict) or block.get("type") != "tool_result":
                            continue
                        tool_use_id = block.get("tool_use_id", "")
                        if tool_use_id in state.current_turn.pending_commands:
                            cmd = state.current_turn.pending_commands.pop(tool_use_id)
                            status = "error" if block.get("is_error") else "success"
                            state.current_turn.resolved_commands.append((cmd, status))
                return
            # Could be a real message with text blocks
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            combined = " ".join(text_parts).strip()
            if combined and not _SYSTEM_TAG_PATTERN.search(combined) and combined != _INTERRUPTED_TEXT:
                state.total_user_messages += 1
                self._flush_turn(state)
                state.current_turn = _TurnAccumulator(
                    timestamp=self._to_local(entry.get("timestamp", "")),
                    user_prompt=combined[:_MAX_PROMPT_LEN],
                )

    def _process_assistant_entry(self, entry: dict, state: _ParseState) -> None:
        """Process an assistant-type JSONL entry."""
        state.total_assistant_messages += 1
        message = entry.get("message", {})
        if not isinstance(message, dict):
            return

        # Extract model (first occurrence wins)
        if not state.model:
            model = message.get("model")
            if model:
                state.model = model

        # Extract token usage with streamed chunk dedup
        usage = message.get("usage", {})
        if usage:
            inp = usage.get("input_tokens", 0)
            out = usage.get("output_tokens", 0)
            cache_r = usage.get("cache_read_input_tokens", 0)
            cache_c = usage.get("cache_creation_input_tokens", 0)

            # Dedup streamed chunks: multiple lines share message.id with cumulative output_tokens
            msg_id = message.get("id", "")
            prev_usage = state.seen_msg_ids.get(msg_id) if msg_id else None

            if prev_usage:
                # Subtract previous values, add current (effectively replaces with latest)
                delta_inp = inp - prev_usage["inp"]
                delta_out = out - prev_usage["out"]
                delta_cache_r = cache_r - prev_usage["cache_r"]
                delta_cache_c = cache_c - prev_usage["cache_c"]
            else:
                delta_inp = inp
                delta_out = out
                delta_cache_r = cache_r
                delta_cache_c = cache_c

            if msg_id:
                state.seen_msg_ids[msg_id] = {
                    "inp": inp, "out": out, "cache_r": cache_r, "cache_c": cache_c,
                }

            state.input_tokens += delta_inp
            state.output_tokens += delta_out
            state.cache_read_tokens += delta_cache_r
            state.cache_creation_tokens += delta_cache_c

            # Context window = input-side tokens of this single API call
            context_window = inp + cache_r + cache_c

            # Accumulate per-turn tokens (buffer if no turn exists yet)
            if state.current_turn:
                state.current_turn.input_tokens += delta_inp
                state.current_turn.output_tokens += delta_out
                state.current_turn.cache_read_tokens += delta_cache_r
                state.current_turn.cache_creation_tokens += delta_cache_c
                # Last API call's context window wins (most up-to-date)
                if context_window > 0:
                    state.current_turn.context_window = context_window
            else:
                state.orphan_input_tokens += delta_inp
                state.orphan_output_tokens += delta_out
                state.orphan_cache_read_tokens += delta_cache_r
                state.orphan_cache_creation_tokens += delta_cache_c

        # Process content blocks
        content = message.get("content", [])
        if not isinstance(content, list):
            return

        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")

            if block_type == "text":
                text = block.get("text", "")
                if text and state.current_turn:
                    state.current_turn.response_texts.append(text)

            elif block_type == "tool_use":
                tool_name = block.get("name", "")
                tool_use_id = block.get("id", "")
                if tool_name:
                    state.total_tool_calls += 1
                    state.tools_summary[tool_name] = state.tools_summary.get(tool_name, 0) + 1
                    if state.current_turn:
                        state.current_turn.tools_used.append(tool_name)

                    # Extract file/command activity
                    tool_input = block.get("input", {})
                    if isinstance(tool_input, dict):
                        self._extract_file_activity(tool_name, tool_input, state)

                        # Per-turn command/file tracking
                        if state.current_turn:
                            if tool_name == "Bash":
                                cmd = tool_input.get("command")
                                if cmd and isinstance(cmd, str) and tool_use_id:
                                    state.current_turn.pending_commands[tool_use_id] = cmd[:_MAX_COMMAND_LEN]
                            elif tool_name in ("Write", "Edit"):
                                path = tool_input.get("file_path")
                                if path and isinstance(path, str):
                                    state.current_turn.files_modified.append(path)

                    # Track Task tool_use_ids for sub-agent attribution
                    if tool_name == "Task" and tool_use_id:
                        state.task_tool_use_ids[tool_use_id] = len(state.turns)

    def _process_progress_entry(self, entry: dict, state: _ParseState) -> None:
        """Process a progress-type JSONL entry (sub-agent messages)."""
        data = entry.get("data", {})
        if not isinstance(data, dict):
            return

        # Only handle agent_progress with assistant messages
        if data.get("type") != "agent_progress":
            return

        inner_msg = data.get("message", {})
        if not isinstance(inner_msg, dict) or inner_msg.get("type") != "assistant":
            return

        # Sub-agent tokens live at data.message.message.usage (doubly nested)
        message = inner_msg.get("message", {})
        if not isinstance(message, dict):
            return

        usage = message.get("usage", {})
        if not usage:
            return

        inp = usage.get("input_tokens", 0)
        out = usage.get("output_tokens", 0)
        cache_c = usage.get("cache_creation_input_tokens", 0)

        # Dedup by sub-agent message.id (sub-agents also stream chunks)
        msg_id = message.get("id", "")
        prev_usage = state.seen_subagent_msg_ids.get(msg_id) if msg_id else None

        if prev_usage:
            delta_inp = inp - prev_usage["inp"]
            delta_out = out - prev_usage["out"]
            delta_cache_c = cache_c - prev_usage["cache_c"]
        else:
            delta_inp = inp
            delta_out = out
            delta_cache_c = cache_c

        if msg_id:
            state.seen_subagent_msg_ids[msg_id] = {
                "inp": inp, "out": out, "cache_c": cache_c,
            }

        # Accumulate session-level sub-agent tokens
        state.subagent_input_tokens += delta_inp
        state.subagent_output_tokens += delta_out
        state.subagent_cache_creation_tokens += delta_cache_c

        # Attribute to turn via toolUseID → task_tool_use_ids mapping
        tool_use_id = entry.get("toolUseID", "")
        turn_idx = state.task_tool_use_ids.get(tool_use_id)

        if turn_idx is not None and turn_idx < len(state.turns):
            # Turn already flushed — update it in place
            turn = state.turns[turn_idx]
            if turn.subagent_tokens is None:
                turn.subagent_tokens = TurnTokens()
            turn.subagent_tokens.input_tokens += delta_inp
            turn.subagent_tokens.output_tokens += delta_out
            turn.subagent_tokens.cache_creation_tokens += delta_cache_c
        elif state.current_turn:
            # Turn still accumulating
            state.current_turn.subagent_input_tokens += delta_inp
            state.current_turn.subagent_output_tokens += delta_out
            state.current_turn.subagent_cache_creation_tokens += delta_cache_c

    def _extract_file_activity(self, tool_name: str, tool_input: dict, state: _ParseState) -> None:
        """Extract file reads, writes, and commands from tool inputs."""
        if tool_name in ("Read", "Glob", "Grep"):
            path = tool_input.get("file_path") or tool_input.get("path")
            if path and isinstance(path, str):
                state.files_read.add(path)
        elif tool_name in ("Write", "Edit"):
            path = tool_input.get("file_path")
            if path and isinstance(path, str):
                state.files_written.add(path)
        elif tool_name == "Bash":
            cmd = tool_input.get("command")
            if cmd and isinstance(cmd, str):
                state.commands_run.append(cmd)

    def _flush_turn(self, state: _ParseState) -> None:
        """Flush accumulated turn data into state.turns."""
        turn = state.current_turn
        if turn is None:
            return

        # Drain orphan tokens (from assistant entries before first user message)
        # into the first turn so that sum(turn.tokens) == session totals.
        if not state.orphan_drained:
            turn.input_tokens += state.orphan_input_tokens
            turn.output_tokens += state.orphan_output_tokens
            turn.cache_read_tokens += state.orphan_cache_read_tokens
            turn.cache_creation_tokens += state.orphan_cache_creation_tokens
            state.orphan_drained = True

        response_summary = ""
        if turn.response_texts:
            combined = " ".join(turn.response_texts)
            response_summary = combined[:_MAX_RESPONSE_LEN]

        turn_tokens = TurnTokens(
            input_tokens=turn.input_tokens,
            output_tokens=turn.output_tokens,
            cache_read_tokens=turn.cache_read_tokens,
            cache_creation_tokens=turn.cache_creation_tokens,
        )

        # Build sub-agent tokens if any
        subagent_tokens = None
        if turn.subagent_input_tokens or turn.subagent_output_tokens or turn.subagent_cache_creation_tokens:
            subagent_tokens = TurnTokens(
                input_tokens=turn.subagent_input_tokens,
                output_tokens=turn.subagent_output_tokens,
                cache_creation_tokens=turn.subagent_cache_creation_tokens,
            )

        # Build commands list: resolved + remaining pending (default success)
        commands: list[TurnCommand] = []
        for cmd, status in turn.resolved_commands:
            commands.append(TurnCommand(command=cmd, status=status))
        for _tool_id, cmd in turn.pending_commands.items():
            commands.append(TurnCommand(command=cmd, status="success"))

        state.turns.append(
            ConversationTurn(
                timestamp=turn.timestamp,
                user_prompt=turn.user_prompt,
                tools_used=turn.tools_used,
                response_summary=response_summary,
                tokens=turn_tokens,
                context_window=turn.context_window,
                subagent_tokens=subagent_tokens,
                commands=commands,
                files_modified=turn.files_modified,
            )
        )
        state.current_turn = None
