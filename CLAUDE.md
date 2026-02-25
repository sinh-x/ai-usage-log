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
├── services/              # Business logic (file I/O + JSONL parsing)
│   ├── structure_service.py       # Dir tree + tracking file init
│   ├── session_service.py         # Session CRUD + batch tools
│   ├── tracking_service.py        # Tracking file updates
│   ├── project_service.py         # Project-level ai-sessions refs
│   ├── stats_service.py           # Aggregate stats from session files
│   ├── claude_session_service.py  # Parse JSONL sessions from ~/.claude/projects/
│   └── jsonl_stats_service.py     # JSONL stats extraction + disk cache
├── tools/                 # MCP tool definitions (8 modules, 19 tools)
│   ├── context_tools.py       # get_session_context
│   ├── session_tools.py       # init/create/update/list/previous + prepare_session, save_session_bundle
│   ├── tracking_tools.py      # update_tracking, get_stats
│   ├── stats_tools.py         # compute_stats
│   ├── claude_session_tools.py    # list/read/batch-read JSONL sessions + get_session_timeline
│   ├── jsonl_stats_tools.py   # extract_session_stats, get_daily_jsonl_stats
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

## Branch Strategy
- **main**: Production releases — auto-versioned via CI on merge
- **develop**: Integration branch — feature PRs merge here
- **feat/**, **fix/**: Feature/bugfix branches off `develop`
- **Never commit directly to main or develop** — always use PRs
- **No version bumps in feature branches** — CI handles versioning on main
- See `.claude/branch-strategy.yaml` for machine-readable config

## Version Control
- **Scheme**: Semantic Versioning (major.minor.patch)
- **Source of truth**: `src/ai_usage_log/__init__.py`
- **Bump tool**: `python tool/bump_version.py [patch|minor|major|X.Y.Z]`
- **Also updates**: `pyproject.toml`, `flake.nix`, `CHANGELOG.md`
- **CI**: GitHub Actions — tests on push to main/develop, auto-release on main

## Design Principles
- **Content-passing**: Agent assembles markdown, MCP writes it. Server doesn't parse session content.
- **Stateless**: No "current session" in server. Agent tracks hash and passes it.
- **Idempotent**: `init_structure` is safe to call multiple times.
- **Sync I/O**: Local SSD operations via `Path` methods.

## 19 MCP Tools
| # | Tool | Purpose |
|---|------|---------|
| 1 | **`prepare_session`** | **Batch: context + dirs + previous + stats + computed + timeline (6-in-1)** |
| 2 | **`save_session_bundle`** | **Batch: create session + tracking + project ref + JSONL cache (4-in-1)** |
| 3 | `list_claude_sessions` | Discover JSONL sessions from ~/.claude/projects/ |
| 4 | `read_claude_session` | Parse full JSONL → structured session data |
| 5 | **`read_claude_sessions`** | **Batch-read multiple JSONL sessions → trimmed summaries** |
| 6 | `get_session_timeline` | Lightweight timeline (timestamps + tools + files) |
| 7 | `extract_session_stats` | Parse JSONL + cache stats to statistics/ dir |
| 8 | `get_daily_jsonl_stats` | Aggregate cached JSONL stats for date range |
| 9 | `update_session` | Update existing session by hash |
| 10 | `list_sessions` | List sessions by date/month/count |
| 11 | `create_daily_summary` | Write daily summary file |
| 12 | `compute_stats` | Aggregate stats from session files (read-only) |
| 13 | `get_session_context` | Detect user, host, terminal, project, cwd, date |
| 14 | `init_structure` | Create dirs + tracking files (idempotent) |
| 15 | `create_session` | Write new session log, return path + hash |
| 16 | `get_previous_session` | Get latest session's open todos |
| 17 | `save_project_ref` | Write project .claude/ai-sessions ref |
| 18 | `update_tracking` | Batch update learning/skills/verification/quiz/stats |
| 19 | `get_stats` | Read statistics.md |
