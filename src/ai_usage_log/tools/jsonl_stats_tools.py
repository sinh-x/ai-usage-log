"""Tools: extract_session_stats, get_daily_jsonl_stats — JSONL stats extraction and aggregation."""

from mcp.server.fastmcp import FastMCP

from ..context import get_context
from ..utils.cache import write_to_cache


def register(mcp: FastMCP) -> None:
    """Register JSONL stats tools."""

    @mcp.tool(
        name="extract_session_stats",
        annotations={
            "title": "Extract Session Stats from JSONL",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def extract_session_stats(
        session_id: str, project_path: str = ""
    ) -> str:
        """Parse a JSONL session, cache stats to statistics/ dir, return structured stats.

        Uses disk cache: if the JSONL hasn't changed since last extraction, returns
        cached result instantly. Otherwise re-parses and updates the cache.

        Args:
            session_id: The session UUID (filename without .jsonl extension).
            project_path: Absolute project path to narrow search. Empty to scan all projects.
        """
        ctx = get_context()
        result = ctx.jsonl_stats.extract_session_stats(
            session_id=session_id, project_path=project_path
        )
        return result.model_dump_json(indent=2)

    @mcp.tool(
        name="get_daily_jsonl_stats",
        annotations={
            "title": "Get Daily JSONL Stats",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_daily_jsonl_stats(
        date: str, date_end: str = "", project_path: str = "", cache_path: str = ""
    ) -> str:
        """Aggregate cached stats from JSONL sessions for a date or date range.

        Scans JSONL files, extracts+caches stats for matching sessions, and returns
        an aggregate with totals, tools histogram, model distribution, and per-session details.

        Always returns a slim response with full data cached to a file.
        If cache_path is empty, data is auto-saved to /tmp/ai-usage-log/get_daily_jsonl_stats-<ts>.json.

        Args:
            date: Start date YYYY-MM-DD.
            date_end: Optional end date YYYY-MM-DD (inclusive). Defaults to same as date.
            project_path: Absolute project path to filter. Empty for all projects.
            cache_path: Path to write full JSON response. Auto-generated in /tmp if empty.
        """
        ctx = get_context()
        result = ctx.jsonl_stats.get_daily_stats(
            date=date, date_end=date_end, project_path=project_path
        )
        return write_to_cache(
            result,
            tool_name="get_daily_jsonl_stats",
            schema_paths=[
                ".date_range (small — date or range string)",
                ".total_sessions (small — count)",
                ".total_duration_minutes (small — float)",
                ".total_input_tokens (small — count)",
                ".total_output_tokens (small — count)",
                ".total_cache_creation_tokens (small — count)",
                ".total_cache_read_tokens (small — count)",
                ".total_tool_calls (small — count)",
                ".tools_histogram (medium — dict of tool to call count)",
                ".model_distribution (medium — dict of model to session count)",
                ".projects (medium — list of project names)",
                ".sessions (large — list of per-session stats)",
                ".cached_count (small — sessions read from cache)",
                ".parsed_count (small — sessions freshly parsed)",
            ],
            cache_path=cache_path,
        )
