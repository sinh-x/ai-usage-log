"""Tool: create_daily_summary."""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ..context import get_context
from ..models.schemas import DailySummaryResult


def register(mcp: FastMCP) -> None:
    """Register daily summary tools."""

    @mcp.tool(
        name="create_daily_summary",
        annotations={
            "title": "Create Daily Summary",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def create_daily_summary(
        year: str, month: str, date: str, content: str
    ) -> str:
        """Write a daily summary file.

        Args:
            year: Four-digit year.
            month: Two-digit month.
            date: Date string YYYY-MM-DD.
            content: Full markdown content for the daily summary.
        """
        ctx = get_context()
        daily_dir = ctx.base_path / "daily" / year / month
        daily_dir.mkdir(parents=True, exist_ok=True)

        filepath = daily_dir / f"{date}-daily.md"
        created = not filepath.exists()
        filepath.write_text(content)

        result = DailySummaryResult(path=str(filepath), created=created)
        return result.model_dump_json(indent=2)
