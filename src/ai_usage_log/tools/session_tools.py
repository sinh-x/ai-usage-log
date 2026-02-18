"""Tools: init_structure, create_session, update_session, list_sessions, get_previous_session, prepare_session, save_session_bundle."""

import os

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
from ..context import get_context
from ..models.schemas import PrepareSessionResult, SaveBundleResult, SessionContext
from ..utils.content import resolve_content


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
        year: str,
        month: str,
        date: str,
        agent: str,
        content: str = "",
        content_path: str = "",
    ) -> str:
        """Create a new session log file. Returns the path, hash, and filename.

        Args:
            year: Four-digit year (e.g. '2026').
            month: Two-digit month (e.g. '02').
            date: Date string YYYY-MM-DD.
            agent: Agent name (e.g. 'claude-code').
            content: Full markdown content for the session log.
            content_path: Path to a file containing the markdown content (alternative to inline content).
        """
        ctx = get_context()
        content = resolve_content(content, content_path)
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
        session_hash: str,
        content: str = "",
        year: str = "",
        month: str = "",
        content_path: str = "",
    ) -> str:
        """Update an existing session log by its hash.

        Args:
            session_hash: The 6-char session hash.
            content: Full updated markdown content.
            year: Optional year to narrow search.
            month: Optional month to narrow search.
            content_path: Path to a file containing the markdown content (alternative to inline content).
        """
        ctx = get_context()
        content = resolve_content(content, content_path)
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

    @mcp.tool(
        name="prepare_session",
        annotations={
            "title": "Prepare Session (Batch)",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def prepare_session(cwd: str = "", year: str = "", month: str = "") -> str:
        """Batch setup for a new session: context + init dirs + previous session + stats.

        Combines get_session_context + init_structure + get_previous_session + get_stats
        into a single call. All original tools remain available individually.

        Args:
            cwd: Current working directory (optional, defaults to server cwd).
            year: Four-digit year (optional, auto-detected if empty).
            month: Two-digit month (optional, auto-detected if empty).
        """
        if not cwd:
            cwd = os.getcwd()
        if not year or not month:
            year, month = get_year_month()

        # 1. Build session context
        context = SessionContext(
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

        # 2. Init directory structure
        ctx = get_context()
        structure = ctx.structure.init_structure(year, month)

        # 3. Get previous session
        previous = ctx.sessions.get_previous_session(year, month)

        # 4. Get stats
        stats = ctx.tracking.get_stats()

        result = PrepareSessionResult(
            context=context,
            structure=structure,
            previous_session=previous,
            stats=stats,
        )
        return result.model_dump_json(indent=2)

    @mcp.tool(
        name="save_session_bundle",
        annotations={
            "title": "Save Session Bundle (Batch)",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def save_session_bundle(
        year: str,
        month: str,
        date: str,
        agent: str,
        content: str = "",
        tracking_updates: dict[str, str] | None = None,
        project_root: str = "",
        user: str = "",
        host: str = "",
        project_ref_content: str = "",
        content_path: str = "",
    ) -> str:
        """Batch save: create session + update tracking + save project ref in one call.

        Combines create_session + update_tracking + save_project_ref.
        All original tools remain available individually.

        Args:
            year: Four-digit year (e.g. '2026').
            month: Two-digit month (e.g. '02').
            date: Date string YYYY-MM-DD.
            agent: Agent name (e.g. 'claude-code').
            content: Full markdown content for the session log.
            tracking_updates: Optional dict of tracking filename -> content.
            project_root: Optional project root path for save_project_ref.
            user: Username for project ref (required if project_root set).
            host: Hostname for project ref (required if project_root set).
            project_ref_content: Markdown content for project ref file.
            content_path: Path to a file containing the session markdown (alternative to inline content).
        """
        ctx = get_context()
        content = resolve_content(content, content_path)

        # 1. Create session
        session_result = ctx.sessions.create_session(year, month, date, agent, content)

        # 2. Update tracking (optional)
        tracking_result = None
        if tracking_updates:
            tracking_result = ctx.tracking.update_tracking(tracking_updates)

        # 3. Save project ref (optional)
        project_ref_result = None
        if project_root and user and host and project_ref_content:
            project_ref_result = ctx.projects.save_project_ref(
                project_root, user, host, project_ref_content
            )

        result = SaveBundleResult(
            session=session_result,
            tracking=tracking_result,
            project_ref=project_ref_result,
        )
        return result.model_dump_json(indent=2)
