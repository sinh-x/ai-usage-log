"""Shared session filename parser."""

from __future__ import annotations


def parse_session_filename(filename: str) -> tuple[str, str, str] | None:
    """Parse YYYY-MM-DD-<hash>-<agent>.md -> (date, hash, agent) or None.

    The agent portion may contain dashes (e.g. "claude-code"), so everything
    after the 4th dash-separated token is joined back as the agent name.
    """
    if not filename.endswith(".md"):
        return None
    stem = filename[:-3]
    parts = stem.split("-")
    # Minimum: YYYY-MM-DD-hash-agent = 5 parts
    if len(parts) < 5:
        return None
    date = f"{parts[0]}-{parts[1]}-{parts[2]}"
    session_hash = parts[3]
    agent = "-".join(parts[4:])
    return date, session_hash, agent
