"""Session CRUD: create, update, find, list."""

import hashlib
import os
from pathlib import Path

from ..models.schemas import (
    PreviousSession,
    SessionInfo,
    SessionList,
    SessionResult,
)
from ..utils.filename import parse_session_filename


class SessionService:
    """Manages session log files."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path

    def _sessions_dir(self, year: str, month: str) -> Path:
        return self.base_path / "sessions" / year / month

    @staticmethod
    def _generate_hash() -> str:
        """Generate a 6-char hex hash from random bytes."""
        return hashlib.md5(os.urandom(256)).hexdigest()[:6]

    @staticmethod
    def _parse_session_filename(filename: str) -> tuple[str, str, str] | None:
        """Parse YYYY-MM-DD-<hash>-<agent>.md -> (date, hash, agent) or None."""
        return parse_session_filename(filename)

    def create_session(
        self, year: str, month: str, date: str, agent: str, content: str
    ) -> SessionResult:
        """Create a new session log file."""
        session_hash = self._generate_hash()
        safe_agent = agent.lower().replace(" ", "-")
        filename = f"{date}-{session_hash}-{safe_agent}.md"
        sessions_dir = self._sessions_dir(year, month)
        sessions_dir.mkdir(parents=True, exist_ok=True)
        filepath = sessions_dir / filename
        filepath.write_text(content)

        return SessionResult(
            path=str(filepath),
            hash=session_hash,
            filename=filename,
            is_new=True,
        )

    def update_session(
        self, session_hash: str, content: str, year: str | None = None, month: str | None = None
    ) -> SessionResult:
        """Update an existing session by hash. Searches recent months if year/month not given."""
        filepath = self._find_by_hash(session_hash, year, month)
        if filepath is None:
            raise FileNotFoundError(f"No session found with hash: {session_hash}")

        filepath.write_text(content)
        return SessionResult(
            path=str(filepath),
            hash=session_hash,
            filename=filepath.name,
            is_new=False,
        )

    def get_session_content(self, session_hash: str, year: str | None = None, month: str | None = None) -> str:
        """Read session content by hash."""
        filepath = self._find_by_hash(session_hash, year, month)
        if filepath is None:
            raise FileNotFoundError(f"No session found with hash: {session_hash}")
        return filepath.read_text()

    def get_previous_session(self, year: str, month: str) -> PreviousSession | None:
        """Get the most recent session file."""
        sessions_dir = self._sessions_dir(year, month)
        if not sessions_dir.exists():
            return None

        files = sorted(sessions_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return None

        latest = files[0]
        parsed = self._parse_session_filename(latest.name)
        if parsed is None:
            return None

        _, session_hash, _ = parsed
        return PreviousSession(
            path=str(latest),
            hash=session_hash,
            filename=latest.name,
            content=latest.read_text(),
        )

    def list_sessions(
        self,
        year: str | None = None,
        month: str | None = None,
        date: str | None = None,
        limit: int = 20,
    ) -> SessionList:
        """List sessions filtered by date/month/count."""
        sessions: list[SessionInfo] = []
        sessions_root = self.base_path / "sessions"

        if not sessions_root.exists():
            return SessionList(sessions=[], count=0)

        # Determine which directories to scan
        if year and month:
            scan_dirs = [self._sessions_dir(year, month)]
        elif year:
            year_dir = sessions_root / year
            scan_dirs = sorted(year_dir.iterdir()) if year_dir.exists() else []
        else:
            # Scan all year/month dirs, most recent first
            scan_dirs = []
            for y_dir in sorted(sessions_root.iterdir(), reverse=True):
                if y_dir.is_dir() and y_dir.name.isdigit():
                    for m_dir in sorted(y_dir.iterdir(), reverse=True):
                        if m_dir.is_dir():
                            scan_dirs.append(m_dir)

        for d in scan_dirs:
            if not d.is_dir():
                continue
            for f in sorted(d.glob("*.md"), reverse=True):
                parsed = self._parse_session_filename(f.name)
                if parsed is None:
                    continue
                file_date, session_hash, agent = parsed
                if date and file_date != date:
                    continue
                sessions.append(
                    SessionInfo(
                        path=str(f),
                        hash=session_hash,
                        filename=f.name,
                        date=file_date,
                        agent=agent,
                    )
                )
                if len(sessions) >= limit:
                    break
            if len(sessions) >= limit:
                break

        return SessionList(sessions=sessions, count=len(sessions))

    def _find_by_hash(self, session_hash: str, year: str | None = None, month: str | None = None) -> Path | None:
        """Find a session file by its hash."""
        sessions_root = self.base_path / "sessions"

        if year and month:
            d = self._sessions_dir(year, month)
            if d.exists():
                for f in d.glob(f"*-{session_hash}-*.md"):
                    return f
            return None

        # Search all directories, most recent first
        if not sessions_root.exists():
            return None
        for y_dir in sorted(sessions_root.iterdir(), reverse=True):
            if not y_dir.is_dir() or not y_dir.name.isdigit():
                continue
            for m_dir in sorted(y_dir.iterdir(), reverse=True):
                if not m_dir.is_dir():
                    continue
                for f in m_dir.glob(f"*-{session_hash}-*.md"):
                    return f
        return None
