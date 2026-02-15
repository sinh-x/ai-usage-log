"""FastMCP entry point — registers all tools and starts the server."""

from mcp.server.fastmcp import FastMCP

from .tools import context_tools, daily_tools, project_tools, session_tools, tracking_tools

mcp = FastMCP("ai_usage_log")

# Register all tool modules
context_tools.register(mcp)
session_tools.register(mcp)
tracking_tools.register(mcp)
project_tools.register(mcp)
daily_tools.register(mcp)


def main() -> None:
    """Entry point for the MCP server (stdio transport)."""
    mcp.run()
