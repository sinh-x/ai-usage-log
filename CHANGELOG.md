# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Version Roadmap

| Version   | Scope                                                    |
|-----------|----------------------------------------------------------|
| **0.x.y** | Pre-stable — building out MCP tools and JSONL parsing    |
| **1.0.0** | Stable MCP server with full session lifecycle management |

## [0.1.1] - 2026-02-25

_No conventional commits since 0.1.0._

## [0.1.0] - 2026-02-15

### Added
- Initial MCP server with 19 tools for AI session logging
- Batch tools: `prepare_session`, `save_session_bundle`
- Claude JSONL session parsing with per-turn token tracking
- Session timeline extraction to prevent timestamp fabrication
- JSONL stats extraction with disk cache
- File-based content passing via `content_path` parameter
- Configurable timezone conversion for session timestamps

[0.1.1]: https://github.com/sinh-x/ai-usage-log/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/sinh-x/ai-usage-log/releases/tag/v0.1.0
