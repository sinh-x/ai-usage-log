"""FastMCP entry point — registers all tools and starts the server."""

from mcp.server.fastmcp import FastMCP

from .tools import claude_session_tools, context_tools, daily_tools, jsonl_stats_tools, project_tools, session_tools, stats_tools, tracking_tools

mcp = FastMCP(
    "ai_usage_log",
    instructions="""AI session logging MCP server. Standard workflow uses 3 tools:
1. prepare_session — batch setup (context + dirs + previous + stats)
2. read_claude_sessions — batch-read JSONL sessions (optional enrichment)
3. save_session_bundle — batch save (session + tracking + project ref)

Also: update_session (updates), list_sessions (discovery), create_daily_summary (daily mode).
Config: AI_USAGE_LOG_PATH env var (default: ~/Documents/ai-usage)""",
)


@mcp.resource("docs://workflow", name="workflow", description="Standard workflow and tool usage guide")
def workflow_docs() -> str:
    """Return the standard workflow and tool usage guide."""
    return """\
# ai-usage-log — Standard Workflow

## Tools (9 active)

| Tool                   | Purpose                                          | Step             |
| ---------------------- | ------------------------------------------------ | ---------------- |
| prepare_session        | Context + dirs + previous + stats (4-in-1)       | Step 0           |
| read_claude_sessions   | Batch-read JSONL sessions → trimmed summaries    | Step 2 (optional)|
| save_session_bundle    | Create session + tracking + project ref (3-in-1) | Step 4           |
| update_session         | Update existing session by hash                  | Step 4 (update)  |
| list_sessions          | List sessions by date/month/count                | On demand        |
| compute_stats          | Aggregate stats from session files (read-only)   | On demand        |
| extract_session_stats  | Parse JSONL + cache stats to statistics/ dir     | On demand        |
| get_daily_jsonl_stats  | Aggregate cached JSONL stats for date range      | On demand        |
| create_daily_summary   | Write daily summary file                         | Daily mode       |

## Standard Flow (2–3 MCP calls)

| Step | MCP Tool               | Purpose                                    |
| ---- | ---------------------- | ------------------------------------------ |
| 0    | prepare_session        | Context + dirs + previous + stats (1 call) |
| 1    | (no MCP)               | Gather session info from user              |
| 2    | read_claude_sessions   | (optional) Enrich with raw session data    |
| 3    | (no MCP)               | Generate markdown + Preview & Confirm      |
| 4    | save_session_bundle    | Save session + tracking + project ref      |
| 5    | (no MCP)               | Confirm to user                            |

## Config

- AI_USAGE_LOG_PATH env var (default: ~/Documents/ai-usage)
"""


# Register all tool modules
claude_session_tools.register(mcp)
context_tools.register(mcp)
session_tools.register(mcp)
tracking_tools.register(mcp)
stats_tools.register(mcp)
jsonl_stats_tools.register(mcp)
project_tools.register(mcp)
daily_tools.register(mcp)


def main() -> None:
    """Entry point for the MCP server (stdio transport)."""
    mcp.run()
