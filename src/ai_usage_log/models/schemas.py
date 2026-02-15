"""Pydantic models for tool responses."""

from pydantic import BaseModel


class SessionContext(BaseModel):
    """Environment context for a new session."""
    user: str
    host: str
    terminal: str
    cwd: str
    project: str | None
    project_root: str | None
    date: str
    time: str
    year: str
    month: str


class StructureResult(BaseModel):
    """Result of init_structure."""
    base_path: str
    created_dirs: list[str]
    created_files: list[str]
    already_existed: bool


class SessionResult(BaseModel):
    """Result of creating or updating a session."""
    path: str
    hash: str
    filename: str
    is_new: bool


class SessionInfo(BaseModel):
    """Summary info for a session file."""
    path: str
    hash: str
    filename: str
    date: str
    agent: str


class SessionList(BaseModel):
    """List of sessions."""
    sessions: list[SessionInfo]
    count: int


class PreviousSession(BaseModel):
    """Previous session with open todos."""
    path: str
    hash: str
    filename: str
    content: str


class TrackingResult(BaseModel):
    """Result of updating tracking files."""
    updated_files: list[str]


class StatsResult(BaseModel):
    """Result of reading statistics."""
    content: str
    path: str


class ProjectRefResult(BaseModel):
    """Result of saving a project reference."""
    path: str
    created: bool


class DailySummaryResult(BaseModel):
    """Result of creating a daily summary."""
    path: str
    created: bool
