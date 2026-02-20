"""Compute aggregate statistics from session files on disk."""

from __future__ import annotations

import re
from pathlib import Path

from ..models.schemas import AgentStats, ComputedStats, MonthlyStats, SessionHeaderMeta
from ..utils.filename import parse_session_filename


class StatsService:
    """Scans session files and computes aggregate statistics."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path

    def compute_stats(
        self,
        year: str | None = None,
        month: str | None = None,
        include_headers: bool = False,
    ) -> ComputedStats:
        """Walk sessions/ dirs, parse filenames, optionally read headers.

        Args:
            year: Optional year filter (e.g. "2026").
            month: Optional month filter (e.g. "02"). Requires year.
            include_headers: If True, also parse Duration/Project from file headers.
        """
        sessions_root = self.base_path / "sessions"

        # Collect raw data per file
        entries: list[dict] = []

        for filepath in self._iter_session_files(sessions_root, year, month):
            parsed = parse_session_filename(filepath.name)
            if parsed is None:
                continue
            date, session_hash, agent = parsed
            entry: dict = {"date": date, "hash": session_hash, "agent": agent, "path": filepath}

            if include_headers:
                header = self._parse_header(filepath)
                entry["header"] = header

            entries.append(entry)

        # Aggregate
        return self._aggregate(entries, include_headers)

    def _iter_session_files(
        self, sessions_root: Path, year: str | None, month: str | None
    ):
        """Yield .md files from sessions/ matching the optional year/month filter."""
        if not sessions_root.exists():
            return

        if year and month:
            month_dir = sessions_root / year / month
            if month_dir.is_dir():
                yield from sorted(month_dir.glob("*.md"))
            return

        if year:
            year_dir = sessions_root / year
            if year_dir.is_dir():
                for m_dir in sorted(year_dir.iterdir()):
                    if m_dir.is_dir():
                        yield from sorted(m_dir.glob("*.md"))
            return

        # All years
        for y_dir in sorted(sessions_root.iterdir()):
            if y_dir.is_dir() and y_dir.name.isdigit():
                for m_dir in sorted(y_dir.iterdir()):
                    if m_dir.is_dir():
                        yield from sorted(m_dir.glob("*.md"))

    @staticmethod
    def _parse_header(filepath: Path) -> SessionHeaderMeta:
        """Best-effort extraction of Duration/Project/Agent from blockquote header lines.

        Handles two formats:
        - Multi-line:  > Duration: ~30 minutes
        - Compressed:  > **Duration:** ~30 minutes | **Project:** foo
        """
        meta = SessionHeaderMeta()
        try:
            # Read only the first 40 lines (headers are at the top)
            text = filepath.read_text(errors="replace")
            lines = text.split("\n", 40)[:40]
        except OSError:
            return meta

        for line in lines:
            stripped = line.strip()
            if not stripped.startswith(">"):
                # Stop scanning once we leave the blockquote header
                if stripped and not stripped.startswith("#"):
                    continue
                continue

            content = stripped.lstrip(">").strip()

            # Multi-line format: "Duration: ~30 minutes"
            # Compressed format: "**Duration:** ~30 minutes | **Project:** foo"
            # Handle both by checking for key patterns

            duration = _extract_field(content, "Duration")
            if duration and meta.duration is None:
                meta.duration = duration
                meta.duration_minutes = _parse_duration_to_minutes(duration)

            project = _extract_field(content, "Project")
            if project and meta.project is None:
                meta.project = project

            agent_detail = _extract_field(content, "Agent")
            if agent_detail and meta.agent_detail is None:
                meta.agent_detail = agent_detail

        return meta

    def _aggregate(self, entries: list[dict], include_headers: bool) -> ComputedStats:
        """Build ComputedStats from raw entries."""
        if not entries:
            return ComputedStats(
                total_sessions=0,
                total_agents=0,
                total_active_days=0,
                date_range="",
                sessions_by_agent={},
                by_month=[],
                by_agent=[],
            )

        # Global counters
        all_dates: set[str] = set()
        agent_counts: dict[str, int] = {}
        agent_dates: dict[str, list[str]] = {}
        month_data: dict[str, dict] = {}  # "YYYY-MM" -> {count, agents, dates, projects}
        total_duration: float = 0.0
        has_duration = False
        all_projects: set[str] = set()

        for entry in entries:
            date = entry["date"]
            agent = entry["agent"]
            month_key = date[:7]  # "YYYY-MM"

            all_dates.add(date)
            agent_counts[agent] = agent_counts.get(agent, 0) + 1
            agent_dates.setdefault(agent, []).append(date)

            # Per-month
            if month_key not in month_data:
                month_data[month_key] = {
                    "count": 0,
                    "agents": {},
                    "dates": {},
                    "projects": set(),
                }
            md = month_data[month_key]
            md["count"] += 1
            md["agents"][agent] = md["agents"].get(agent, 0) + 1
            md["dates"][date] = md["dates"].get(date, 0) + 1

            if include_headers and "header" in entry:
                header: SessionHeaderMeta = entry["header"]
                if header.duration_minutes is not None:
                    total_duration += header.duration_minutes
                    has_duration = True
                if header.project:
                    all_projects.add(header.project)
                    md["projects"].add(header.project)

        sorted_dates = sorted(all_dates)
        date_range = f"{sorted_dates[0]} to {sorted_dates[-1]}" if len(sorted_dates) > 1 else sorted_dates[0]

        # Build by_month
        by_month = []
        for mk in sorted(month_data.keys()):
            md = month_data[mk]
            by_month.append(
                MonthlyStats(
                    month=mk,
                    session_count=md["count"],
                    sessions_by_agent=md["agents"],
                    sessions_by_date=md["dates"],
                    active_days=len(md["dates"]),
                    projects=sorted(md["projects"]),
                )
            )

        # Build by_agent
        by_agent = []
        for agent in sorted(agent_counts.keys()):
            by_agent.append(
                AgentStats(
                    agent=agent,
                    session_count=agent_counts[agent],
                    dates=sorted(set(agent_dates[agent])),
                )
            )

        return ComputedStats(
            total_sessions=len(entries),
            total_agents=len(agent_counts),
            total_active_days=len(all_dates),
            date_range=date_range,
            sessions_by_agent=agent_counts,
            by_month=by_month,
            by_agent=by_agent,
            total_duration_minutes=total_duration if has_duration else None,
            projects=sorted(all_projects) if include_headers else None,
        )


def _extract_field(text: str, field_name: str) -> str | None:
    """Extract a field value from blockquote content.

    Matches both:
    - "Duration: ~30 minutes"
    - "**Duration:** ~30 minutes"
    """
    # Match: optional ** before name, colon inside or outside **, then value until | or end
    pattern = rf"\*{{0,2}}{field_name}:?\*{{0,2}}:?\s*(.+?)(?:\s*\||\s*$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _parse_duration_to_minutes(raw: str) -> float | None:
    """Convert duration strings like '~30 minutes', '~1.5 hours', '~2 hours' to float minutes."""
    raw = raw.strip().lstrip("~").strip()

    # Try "N hours" / "N hour"
    match = re.match(r"([\d.]+)\s*hours?", raw, re.IGNORECASE)
    if match:
        return float(match.group(1)) * 60

    # Try "N minutes" / "N mins" / "N min"
    match = re.match(r"([\d.]+)\s*min(?:ute)?s?", raw, re.IGNORECASE)
    if match:
        return float(match.group(1))

    return None
