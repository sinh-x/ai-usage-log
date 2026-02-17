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


# --- Claude JSONL session models ---


class TurnTokens(BaseModel):
    """Token usage for a single conversation turn."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_creation_tokens


class ConversationTurn(BaseModel):
    """A single user→assistant conversation turn."""
    timestamp: str
    user_prompt: str
    tools_used: list[str]
    response_summary: str
    tokens: TurnTokens | None = None


class ClaudeSessionData(BaseModel):
    """Full parsed data from a Claude Code JSONL session."""
    session_id: str
    project_path: str
    project_name: str
    git_branch: str | None
    model: str | None
    start_time: str
    end_time: str
    duration_minutes: float
    conversation: list[ConversationTurn]
    total_user_messages: int
    total_assistant_messages: int
    total_tool_calls: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    tools_summary: dict[str, int]
    files_read: list[str]
    files_written: list[str]
    commands_run: list[str]


class ClaudeSessionInfo(BaseModel):
    """Summary info for a Claude Code JSONL session."""
    session_id: str
    project_path: str
    project_name: str
    start_time: str | None
    message_count: int
    git_branch: str | None
    is_current: bool


class ClaudeSessionList(BaseModel):
    """List of discovered Claude Code sessions."""
    sessions: list[ClaudeSessionInfo]
    count: int
