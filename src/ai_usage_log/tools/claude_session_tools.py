"""Tools: list_claude_sessions, read_claude_session — read Claude Code JSONL sessions."""

from mcp.server.fastmcp import FastMCP

from ..config.settings import get_tz_offset
from ..services.claude_session_service import ClaudeSessionService


def register(mcp: FastMCP) -> None:
    """Register Claude session tools."""

    service = ClaudeSessionService(tz_offset_hours=get_tz_offset())

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
    async def read_claude_session(session_id: str, project_path: str = "") -> str:
        """Parse JSONL session and return structured data for summarization.

        Args:
            session_id: The session UUID (filename without .jsonl extension).
            project_path: Absolute project path to narrow search. Empty to scan all projects.
        """
        result = service.read_session(session_id=session_id, project_path=project_path)
        return result.model_dump_json(indent=2)
