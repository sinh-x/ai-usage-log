"""Tool: save_project_ref."""

from mcp.server.fastmcp import FastMCP

from ..context import get_context


def register(mcp: FastMCP) -> None:
    """Register project tools."""

    @mcp.tool(
        name="save_project_ref",
        annotations={
            "title": "Save Project Reference",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def save_project_ref(
        project_root: str, user: str, host: str, content: str
    ) -> str:
        """Write or update the project .claude/ai-sessions reference file.

        Args:
            project_root: Absolute path to the git project root.
            user: Username (e.g. 'sinh').
            host: Hostname (e.g. 'Drgnfly').
            content: Full markdown content for the ai-sessions file.
        """
        ctx = get_context()
        result = ctx.projects.save_project_ref(project_root, user, host, content)
        return result.model_dump_json(indent=2)
