"""Tools: compute_stats."""

from mcp.server.fastmcp import FastMCP

from ..context import get_context


def register(mcp: FastMCP) -> None:
    """Register stats computation tools."""

    @mcp.tool(
        name="compute_stats",
        annotations={
            "title": "Compute Session Statistics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def compute_stats(
        year: str = "",
        month: str = "",
        include_headers: bool = False,
    ) -> str:
        """Compute aggregate statistics from session files on disk.

        Two modes:
        - Filename-only (default): counts by month/agent/date from filenames alone.
        - Header-enriched (include_headers=True): also parses Duration and Project
          from session file headers.

        Args:
            year: Optional year filter (e.g. '2026').
            month: Optional month filter (e.g. '02'). Requires year.
            include_headers: If True, read file headers for duration/project data.
        """
        ctx = get_context()
        result = ctx.stats.compute_stats(
            year=year or None,
            month=month or None,
            include_headers=include_headers,
        )
        return result.model_dump_json(indent=2)
