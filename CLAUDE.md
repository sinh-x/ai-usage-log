# ai-usage-log MCP Server

## What This Is
An MCP server that handles file I/O for AI session logging. The AI agent (via the `/ai-usage-log` skill) assembles markdown content and calls these tools to write it to disk.

## Architecture
```
src/ai_usage_log/
├── server.py              # FastMCP entry point, registers all tools
├── context.py             # ServerContext singleton (services + config)
├── config/settings.py     # Base path, terminal/project detection
├── models/schemas.py      # Pydantic response models
├── services/              # Business logic (file I/O)
│   ├── structure_service.py   # Dir tree + tracking file init
│   ├── session_service.py     # Session CRUD
│   ├── tracking_service.py    # Tracking file updates
│   └── project_service.py     # Project-level ai-sessions refs
├── tools/                 # MCP tool definitions (5 modules, 10 tools)
│   ├── context_tools.py       # get_session_context
│   ├── session_tools.py       # init_structure, create/update/list/previous
│   ├── tracking_tools.py      # update_tracking, get_stats
│   ├── project_tools.py       # save_project_ref
│   └── daily_tools.py         # create_daily_summary
└── templates/file_templates.py  # Tracking file init templates
```

## Build & Run
```bash
poetry install
poetry run ai-usage-log          # stdio transport
python -m py_compile src/ai_usage_log/server.py  # compile check
poetry run pytest                # tests
```

## Config
Single env var: `AI_USAGE_LOG_PATH` (default: `~/Documents/ai-usage`)

## Design Principles
- **Content-passing**: Agent assembles markdown, MCP writes it. Server doesn't parse session content.
- **Stateless**: No "current session" in server. Agent tracks hash and passes it.
- **Idempotent**: `init_structure` is safe to call multiple times.
- **Sync I/O**: Local SSD operations via `Path` methods.

## 10 MCP Tools
| # | Tool | Purpose |
|---|------|---------|
| 1 | `get_session_context` | Detect user, host, terminal, project, cwd, date |
| 2 | `init_structure` | Create dirs + tracking files (idempotent) |
| 3 | `create_session` | Write new session log, return path + hash |
| 4 | `update_session` | Update existing session by hash |
| 5 | `get_previous_session` | Get latest session's open todos |
| 6 | `list_sessions` | List sessions by date/month/count |
| 7 | `save_project_ref` | Write project .claude/ai-sessions ref |
| 8 | `update_tracking` | Batch update learning/skills/verification/quiz/stats |
| 9 | `get_stats` | Read statistics.md |
| 10 | `create_daily_summary` | Write daily summary file |
