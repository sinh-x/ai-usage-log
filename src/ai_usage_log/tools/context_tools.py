"""Tool: get_session_context — detect environment for a new session."""

from mcp.server.fastmcp import FastMCP

from ..config.settings import (
    detect_project,
    detect_project_root,
    get_host,
    get_now,
    get_terminal_session,
    get_today,
    get_user,
    get_year_month,
)
from ..models.schemas import SessionContext


def register(mcp: FastMCP) -> None:
    """Register context tools."""

    @mcp.tool(
        name="get_session_context",
        annotations={
            "title": "Get Session Context",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_session_context(cwd: str = "") -> str:
        """Detect user, host, terminal, project, cwd, date/time.

        Args:
            cwd: Current working directory (optional, defaults to server cwd).
        """
        import os

        if not cwd:
            cwd = os.getcwd()

        year, month = get_year_month()
        ctx = SessionContext(
            user=get_user(),
            host=get_host(),
            terminal=get_terminal_session(),
            cwd=cwd,
            project=detect_project(cwd),
            project_root=detect_project_root(cwd),
            date=get_today(),
            time=get_now(),
            year=year,
            month=month,
        )
        return ctx.model_dump_json(indent=2)
