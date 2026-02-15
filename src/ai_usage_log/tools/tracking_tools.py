"""Tools: update_tracking, get_stats."""

from mcp.server.fastmcp import FastMCP

from ..context import get_context


def register(mcp: FastMCP) -> None:
    """Register tracking tools."""

    @mcp.tool(
        name="update_tracking",
        annotations={
            "title": "Update Tracking Files",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def update_tracking(updates: dict[str, str]) -> str:
        """Batch update tracking files (learning, skills, verification, quiz, stats).

        Args:
            updates: Dict mapping filename to new full content.
                     Valid keys: learning-queue.md, skills-gained.md,
                     verification-queue.md, quiz-bank.md, statistics.md
        """
        ctx = get_context()
        result = ctx.tracking.update_tracking(updates)
        return result.model_dump_json(indent=2)

    @mcp.tool(
        name="get_stats",
        annotations={
            "title": "Get Statistics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_stats() -> str:
        """Read the current statistics.md file content."""
        ctx = get_context()
        result = ctx.tracking.get_stats()
        return result.model_dump_json(indent=2)
