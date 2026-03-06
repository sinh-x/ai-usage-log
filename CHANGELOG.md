# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Version Roadmap

| Version   | Scope                                                    |
|-----------|----------------------------------------------------------|
| **0.x.y** | Pre-stable — building out MCP tools and JSONL parsing    |
| **1.0.0** | Stable MCP server with full session lifecycle management |

## [0.2.0] - 2026-03-06

### Added
- `server_version` field in `SessionContext` — sessions now record which MCP server version created them (#1)
- Version exposed via `get_session_context` and `prepare_session` tools

### Fixed
- `read_claude_sessions` now falls through to scan all project directories when encoded project path doesn't match (#7)
- `_get_project_dir` accepts already-encoded directory names without double-encoding

## [0.1.0] - 2026-02-15

### Added
- Initial MCP server with 19 tools for AI session logging
- Batch tools: `prepare_session`, `save_session_bundle`
- Claude JSONL session parsing with per-turn token tracking
- Session timeline extraction to prevent timestamp fabrication
- JSONL stats extraction with disk cache
- File-based content passing via `content_path` parameter
- Configurable timezone conversion for session timestamps

[0.2.0]: https://github.com/sinh-x/ai-usage-log/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/sinh-x/ai-usage-log/releases/tag/v0.1.0
