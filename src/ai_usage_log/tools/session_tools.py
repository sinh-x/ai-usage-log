"""Tools: init_structure, create_session, update_session, list_sessions, get_previous_session."""

from mcp.server.fastmcp import FastMCP

from ..context import get_context


def register(mcp: FastMCP) -> None:
    """Register session-related tools."""

    @mcp.tool(
        name="init_structure",
        annotations={
            "title": "Initialize Directory Structure",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def init_structure(year: str, month: str) -> str:
        """Create the ai-usage directory tree and tracking files. Safe to call multiple times.

        Args:
            year: Four-digit year (e.g. '2026').
            month: Two-digit month (e.g. '02').
        """
        ctx = get_context()
        result = ctx.structure.init_structure(year, month)
        return result.model_dump_json(indent=2)

    @mcp.tool(
        name="create_session",
        annotations={
            "title": "Create Session Log",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def create_session(
        year: str, month: str, date: str, agent: str, content: str
    ) -> str:
        """Create a new session log file. Returns the path, hash, and filename.

        Args:
            year: Four-digit year (e.g. '2026').
            month: Two-digit month (e.g. '02').
            date: Date string YYYY-MM-DD.
            agent: Agent name (e.g. 'claude-code').
            content: Full markdown content for the session log.
        """
        ctx = get_context()
        result = ctx.sessions.create_session(year, month, date, agent, content)
        return result.model_dump_json(indent=2)

    @mcp.tool(
        name="update_session",
        annotations={
            "title": "Update Session Log",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def update_session(
        session_hash: str, content: str, year: str = "", month: str = ""
    ) -> str:
        """Update an existing session log by its hash.

        Args:
            session_hash: The 6-char session hash.
            content: Full updated markdown content.
            year: Optional year to narrow search.
            month: Optional month to narrow search.
        """
        ctx = get_context()
        try:
            result = ctx.sessions.update_session(
                session_hash,
                content,
                year=year or None,
                month=month or None,
            )
            return result.model_dump_json(indent=2)
        except FileNotFoundError as e:
            return f"Error: {e}"

    @mcp.tool(
        name="get_previous_session",
        annotations={
            "title": "Get Previous Session",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_previous_session(year: str, month: str) -> str:
        """Get the most recent session log's content and metadata.

        Args:
            year: Four-digit year.
            month: Two-digit month.
        """
        ctx = get_context()
        result = ctx.sessions.get_previous_session(year, month)
        if result is None:
            return "No previous sessions found."
        return result.model_dump_json(indent=2)

    @mcp.tool(
        name="list_sessions",
        annotations={
            "title": "List Sessions",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def list_sessions(
        year: str = "", month: str = "", date: str = "", limit: int = 20
    ) -> str:
        """List session logs filtered by date, month, or count.

        Args:
            year: Optional year filter.
            month: Optional month filter (requires year).
            date: Optional date filter YYYY-MM-DD.
            limit: Max number of results (default 20).
        """
        ctx = get_context()
        result = ctx.sessions.list_sessions(
            year=year or None,
            month=month or None,
            date=date or None,
            limit=limit,
        )
        return result.model_dump_json(indent=2)
