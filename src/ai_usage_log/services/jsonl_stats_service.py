"""Service for extracting, caching, and aggregating stats from Claude JSONL sessions."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from ..models.schemas import CachedSessionStats, ClaudeSessionData, DailyAggregate
from .claude_session_service import ClaudeSessionService

# Sanitise project names for use in filenames
_FILENAME_UNSAFE = re.compile(r"[^a-zA-Z0-9_-]")


class JsonlStatsService:
    """Extract stats from JSONL sessions, cache to disk, and aggregate."""

    def __init__(
        self,
        statistics_dir: Path,
        claude_session_service: ClaudeSessionService,
    ) -> None:
        self.statistics_dir = statistics_dir
        self.claude = claude_session_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_session_stats(
        self, session_id: str, project_path: str = ""
    ) -> CachedSessionStats:
        """Check cache -> parse if stale -> save -> return CachedSessionStats."""
        jsonl_path = self.claude.find_session_file(session_id, project_path)
        if jsonl_path is None:
            raise FileNotFoundError(f"No JSONL session found: {session_id}")

        jsonl_mtime = jsonl_path.stat().st_mtime

        # Try cache
        cached = self._find_cached(session_id)
        if cached is not None and self._is_cache_valid(cached, jsonl_mtime):
            return cached

        # Parse fresh
        data = self.claude.read_session(session_id, project_path)
        stats = self._to_cached_stats(data, jsonl_mtime, str(jsonl_path))
        self._save_cache(stats)
        return stats

    def get_daily_stats(
        self,
        date: str,
        date_end: str = "",
        project_path: str = "",
    ) -> DailyAggregate:
        """Discover sessions by date(s) -> extract+cache each -> aggregate."""
        start_date = datetime.strptime(date, "%Y-%m-%d").date()
        end_date = (
            datetime.strptime(date_end, "%Y-%m-%d").date() if date_end else start_date
        )

        date_range_str = date if not date_end or date == date_end else f"{date} to {date_end}"

        # Discover all JSONL files and filter by date
        matching: list[tuple[str, str, Path]] = []  # (session_id, project_path_str, jsonl_path)
        dirs_to_scan = self._get_scan_dirs(project_path)

        for proj_dir, encoded_name in dirs_to_scan:
            proj_path_str = project_path or encoded_name
            for jf in proj_dir.glob("*.jsonl"):
                session_date = self._get_session_date(jf)
                if session_date is None:
                    continue
                if start_date <= session_date <= end_date:
                    matching.append((jf.stem, proj_path_str, jf))

        # Extract stats for each matching session
        sessions: list[CachedSessionStats] = []
        cached_count = 0
        parsed_count = 0

        for session_id, proj_path_str, jsonl_path in matching:
            jsonl_mtime = jsonl_path.stat().st_mtime
            cached = self._find_cached(session_id)
            if cached is not None and self._is_cache_valid(cached, jsonl_mtime):
                sessions.append(cached)
                cached_count += 1
            else:
                try:
                    data = self.claude.read_session(session_id, proj_path_str)
                    stats = self._to_cached_stats(data, jsonl_mtime, str(jsonl_path))
                    self._save_cache(stats)
                    sessions.append(stats)
                    parsed_count += 1
                except Exception:
                    continue

        return self._aggregate(sessions, date_range_str, cached_count, parsed_count)

    def extract_and_link(
        self, jsonl_session_ids: list[str], project_path: str = ""
    ) -> list[CachedSessionStats]:
        """Extract stats for multiple JSONL sessions. Used by save_session_bundle."""
        results: list[CachedSessionStats] = []
        for sid in jsonl_session_ids:
            try:
                stats = self.extract_session_stats(sid, project_path)
                results.append(stats)
            except FileNotFoundError:
                continue
        return results

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _cache_path(self, session_id: str, date: str, project_name: str) -> Path:
        """Build {statistics_dir}/{date}--{project}--{session_id}.json."""
        safe_project = _FILENAME_UNSAFE.sub("-", project_name).strip("-") or "unknown"
        return self.statistics_dir / f"{date}--{safe_project}--{session_id}.json"

    def _find_cached(self, session_id: str) -> CachedSessionStats | None:
        """Glob for *--*--{session_id}.json in statistics dir."""
        if not self.statistics_dir.is_dir():
            return None
        matches = list(self.statistics_dir.glob(f"*--*--{session_id}.json"))
        if not matches:
            return None
        try:
            raw = matches[0].read_text()
            return CachedSessionStats.model_validate_json(raw)
        except Exception:
            # Corrupt cache — will be re-parsed
            return None

    def _is_cache_valid(self, cached: CachedSessionStats, jsonl_mtime: float) -> bool:
        """Compare jsonl_mtime in cache vs actual."""
        return cached.jsonl_mtime == jsonl_mtime

    def _save_cache(self, stats: CachedSessionStats) -> None:
        """Write JSON cache file."""
        date = stats.start_time[:10] if len(stats.start_time) >= 10 else "unknown"
        path = self._cache_path(stats.session_id, date, stats.project_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stats.model_dump_json(indent=2))

    # ------------------------------------------------------------------
    # Date extraction (fast — reads only first timestamp)
    # ------------------------------------------------------------------

    def _get_session_date(self, jsonl_path: Path) -> date | None:
        """Read only the first timestamp from a JSONL file to determine session date."""
        try:
            with open(jsonl_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("timestamp")
                    if ts:
                        # Apply TZ conversion if configured
                        local_ts = self.claude._to_local(ts)
                        return datetime.fromisoformat(
                            local_ts.replace("Z", "+00:00")
                        ).date()
        except OSError:
            pass
        return None

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _to_cached_stats(
        self, data: ClaudeSessionData, jsonl_mtime: float, jsonl_path: str
    ) -> CachedSessionStats:
        """Convert ClaudeSessionData -> CachedSessionStats."""
        return CachedSessionStats(
            session_id=data.session_id,
            project_name=data.project_name,
            project_path=data.project_path,
            git_branch=data.git_branch,
            model=data.model,
            start_time=data.start_time,
            end_time=data.end_time,
            duration_minutes=data.duration_minutes,
            total_user_messages=data.total_user_messages,
            total_assistant_messages=data.total_assistant_messages,
            total_tool_calls=data.total_tool_calls,
            input_tokens=data.input_tokens,
            output_tokens=data.output_tokens,
            cache_creation_tokens=data.cache_creation_tokens,
            cache_read_tokens=data.cache_read_tokens,
            subagent_input_tokens=data.subagent_input_tokens,
            subagent_output_tokens=data.subagent_output_tokens,
            subagent_cache_creation_tokens=data.subagent_cache_creation_tokens,
            tools_summary=dict(data.tools_summary),
            jsonl_mtime=jsonl_mtime,
            jsonl_path=jsonl_path,
        )

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _aggregate(
        self,
        sessions: list[CachedSessionStats],
        date_range: str,
        cached_count: int,
        parsed_count: int,
    ) -> DailyAggregate:
        """Aggregate a list of CachedSessionStats into a DailyAggregate."""
        tools_histogram: dict[str, int] = {}
        model_distribution: dict[str, int] = {}
        projects: set[str] = set()

        total_duration = 0.0
        total_input = 0
        total_output = 0
        total_cache_creation = 0
        total_cache_read = 0
        total_subagent_input = 0
        total_subagent_output = 0
        total_subagent_cache_creation = 0
        total_tool_calls = 0
        total_user_messages = 0
        total_assistant_messages = 0

        for s in sessions:
            total_duration += s.duration_minutes
            total_input += s.input_tokens
            total_output += s.output_tokens
            total_cache_creation += s.cache_creation_tokens
            total_cache_read += s.cache_read_tokens
            total_subagent_input += s.subagent_input_tokens
            total_subagent_output += s.subagent_output_tokens
            total_subagent_cache_creation += s.subagent_cache_creation_tokens
            total_tool_calls += s.total_tool_calls
            total_user_messages += s.total_user_messages
            total_assistant_messages += s.total_assistant_messages

            for tool, count in s.tools_summary.items():
                tools_histogram[tool] = tools_histogram.get(tool, 0) + count

            if s.model:
                model_distribution[s.model] = model_distribution.get(s.model, 0) + 1

            projects.add(s.project_name)

        return DailyAggregate(
            date_range=date_range,
            total_sessions=len(sessions),
            total_duration_minutes=round(total_duration, 1),
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cache_creation_tokens=total_cache_creation,
            total_cache_read_tokens=total_cache_read,
            total_subagent_input_tokens=total_subagent_input,
            total_subagent_output_tokens=total_subagent_output,
            total_subagent_cache_creation_tokens=total_subagent_cache_creation,
            total_tool_calls=total_tool_calls,
            total_user_messages=total_user_messages,
            total_assistant_messages=total_assistant_messages,
            tools_histogram=tools_histogram,
            model_distribution=model_distribution,
            projects=sorted(projects),
            sessions=sessions,
            cached_count=cached_count,
            parsed_count=parsed_count,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_scan_dirs(self, project_path: str) -> list[tuple[Path, str]]:
        """Return list of (project_dir, encoded_name) to scan."""
        if project_path:
            proj_dir = self.claude._get_project_dir(project_path)
            if proj_dir is None:
                return []
            return [(proj_dir, proj_dir.name)]

        if not self.claude.claude_projects_dir.is_dir():
            return []
        return [
            (d, d.name)
            for d in sorted(self.claude.claude_projects_dir.iterdir())
            if d.is_dir()
        ]
