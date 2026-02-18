"""Tool: create_daily_summary."""


from mcp.server.fastmcp import FastMCP

from ..context import get_context
from ..models.schemas import DailySummaryResult
from ..utils.content import resolve_content


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
        year: str, month: str, date: str, content: str = "", content_path: str = ""
    ) -> str:
        """Write a daily summary file.

        Args:
            year: Four-digit year.
            month: Two-digit month.
            date: Date string YYYY-MM-DD.
            content: Full markdown content for the daily summary.
            content_path: Path to a file containing the markdown content (alternative to inline content).
        """
        content = resolve_content(content, content_path)
        ctx = get_context()
        daily_dir = ctx.base_path / "daily" / year / month
        daily_dir.mkdir(parents=True, exist_ok=True)

        filepath = daily_dir / f"{date}-daily.md"
        created = not filepath.exists()
        filepath.write_text(content)

        result = DailySummaryResult(path=str(filepath), created=created)
        return result.model_dump_json(indent=2)
