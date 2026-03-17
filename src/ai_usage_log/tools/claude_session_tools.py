"""Tools: list_claude_sessions, read_claude_session, read_claude_sessions — read Claude Code JSONL sessions."""

from mcp.server.fastmcp import FastMCP

from ..context import get_context
from ..models.schemas import ClaudeSessionsBatchResult
from ..utils.cache import write_to_cache


def register(mcp: FastMCP) -> None:
    """Register Claude session tools."""

    @mcp.tool(
        name="list_claude_sessions",
        annotations={
            "title": "List Claude Sessions",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def list_claude_sessions(project_path: str = "", limit: int = 20) -> str:
        """Discover Claude Code sessions from ~/.claude/projects/.

        Args:
            project_path: Absolute project path to filter (e.g. /home/user/myproject). Empty for all.
            limit: Maximum number of sessions to return (default 20).
        """
        service = get_context().claude_sessions
        result = service.list_sessions(project_path=project_path, limit=limit)
        return result.model_dump_json(indent=2)

    @mcp.tool(
        name="read_claude_session",
        annotations={
            "title": "Read Claude Session",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def read_claude_session(session_id: str, project_path: str = "", cache_path: str = "") -> str:
        """Parse JSONL session and return structured data for summarization.

        Always returns a slim response with full data cached to a file.
        If cache_path is empty, data is auto-saved to /tmp/ai-usage-log/read_claude_session-<ts>.json.

        Args:
            session_id: The session UUID (filename without .jsonl extension).
            project_path: Absolute project path to narrow search. Empty to scan all projects.
            cache_path: Path to write full JSON response. Auto-generated in /tmp if empty.
        """
        service = get_context().claude_sessions
        result = service.read_session(session_id=session_id, project_path=project_path)
        return write_to_cache(
            result,
            tool_name="read_claude_session",
            schema_paths=[
                ".session_id (small — UUID)",
                ".project_name (small — project name)",
                ".git_branch (small — branch name)",
                ".model (small — model ID)",
                ".start_time (small — ISO timestamp)",
                ".end_time (small — ISO timestamp)",
                ".duration_minutes (small — float)",
                ".conversation (large — list of turns with prompts, tools, tokens)",
                ".total_tool_calls (small — count)",
                ".input_tokens (small — count)",
                ".output_tokens (small — count)",
                ".tools_summary (medium — dict of tool name to call count)",
                ".files_read (medium — list of file paths)",
                ".files_written (medium — list of file paths)",
                ".commands_run (medium — list of commands)",
            ],
            cache_path=cache_path,
        )

    @mcp.tool(
        name="get_session_timeline",
        annotations={
            "title": "Get Session Timeline",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_session_timeline(
        session_id: str, project_path: str = "", cache_path: str = ""
    ) -> str:
        """Extract a lightweight timeline from a JSONL session for use in session logs.

        Returns only timestamps, user prompts, tools used, and files modified —
        the minimum needed for writing accurate session log timelines without
        fabricating timestamps.

        Always returns a slim response with full data cached to a file.
        If cache_path is empty, data is auto-saved to /tmp/ai-usage-log/get_session_timeline-<ts>.json.

        Args:
            session_id: The session UUID (filename without .jsonl extension).
            project_path: Absolute project path to narrow search. Empty to scan all projects.
            cache_path: Path to write full JSON response. Auto-generated in /tmp if empty.
        """
        service = get_context().claude_sessions
        result = service.get_timeline(session_id=session_id, project_path=project_path)
        return write_to_cache(
            result,
            tool_name="get_session_timeline",
            schema_paths=[
                ".session_id (small — UUID)",
                ".project_name (small — project name)",
                ".start_time (small — ISO timestamp)",
                ".end_time (small — ISO timestamp)",
                ".duration_minutes (small — float)",
                ".entries (large — list of timeline entries with timestamps, tools, files)",
                ".entries[0].timestamp (small — RFC3339 timestamp of first entry)",
            ],
            cache_path=cache_path,
        )

    @mcp.tool(
        name="read_claude_sessions",
        annotations={
            "title": "Read Claude Sessions (Batch)",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def read_claude_sessions(
        session_ids: list[str], project_path: str = "", cache_path: str = ""
    ) -> str:
        """Batch-read multiple JSONL sessions and return trimmed summaries.

        Always returns a slim response with full data cached to a file.
        If cache_path is empty, data is auto-saved to /tmp/ai-usage-log/read_claude_sessions-<ts>.json.

        Args:
            session_ids: List of session UUIDs to read.
            project_path: Absolute project path to narrow search. Empty to scan all projects.
            cache_path: Path to write full JSON response. Auto-generated in /tmp if empty.
        """
        service = get_context().claude_sessions
        summaries = []
        for sid in session_ids:
            data = service.read_session(session_id=sid, project_path=project_path)
            summaries.append(data.to_summary())

        result = ClaudeSessionsBatchResult(sessions=summaries, count=len(summaries))
        return write_to_cache(
            result,
            tool_name="read_claude_sessions",
            schema_paths=[
                ".count (small — number of sessions)",
                ".sessions (large — list of session summaries)",
                ".sessions[0].session_id (small — UUID of first session)",
                ".sessions[0].project_name (small — project of first session)",
                ".sessions[0].duration_minutes (small — duration of first session)",
                ".sessions[0].tools_summary (medium — tool call counts for first session)",
                ".sessions[0].conversation (large — turns of first session)",
            ],
            cache_path=cache_path,
        )
