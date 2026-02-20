"""Pydantic models for tool responses."""

from __future__ import annotations

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


class SessionHeaderMeta(BaseModel):
    """Metadata parsed from a session file's blockquote header."""
    duration: str | None = None
    duration_minutes: float | None = None
    project: str | None = None
    agent_detail: str | None = None


class MonthlyStats(BaseModel):
    """Aggregate stats for a single month."""
    month: str
    session_count: int
    sessions_by_agent: dict[str, int]
    sessions_by_date: dict[str, int]
    active_days: int
    projects: list[str]


class AgentStats(BaseModel):
    """Aggregate stats for a single agent."""
    agent: str
    session_count: int
    dates: list[str]


class ComputedStats(BaseModel):
    """Aggregate statistics computed from session files on disk."""
    total_sessions: int
    total_agents: int
    total_active_days: int
    date_range: str
    sessions_by_agent: dict[str, int]
    by_month: list[MonthlyStats]
    by_agent: list[AgentStats]
    total_duration_minutes: float | None = None
    projects: list[str] | None = None


class CachedSessionStats(BaseModel):
    """Per-session stats extracted from JSONL, saved to statistics/ dir."""
    session_id: str
    project_name: str
    project_path: str
    git_branch: str | None
    model: str | None
    start_time: str
    end_time: str
    duration_minutes: float
    total_user_messages: int
    total_assistant_messages: int
    total_tool_calls: int
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    subagent_input_tokens: int
    subagent_output_tokens: int
    subagent_cache_creation_tokens: int
    tools_summary: dict[str, int]
    jsonl_mtime: float
    jsonl_path: str


class DailyAggregate(BaseModel):
    """Aggregated stats for a date or date range."""
    date_range: str
    total_sessions: int
    total_duration_minutes: float
    total_input_tokens: int
    total_output_tokens: int
    total_cache_creation_tokens: int
    total_cache_read_tokens: int
    total_subagent_input_tokens: int
    total_subagent_output_tokens: int
    total_subagent_cache_creation_tokens: int
    total_tool_calls: int
    total_user_messages: int
    total_assistant_messages: int
    tools_histogram: dict[str, int]
    model_distribution: dict[str, int]
    projects: list[str]
    sessions: list[CachedSessionStats]
    cached_count: int
    parsed_count: int


class PrepareSessionResult(BaseModel):
    """Result of prepare_session batch tool."""
    context: SessionContext
    structure: StructureResult
    previous_session: PreviousSession | None
    stats: StatsResult
    computed_stats: ComputedStats | None = None


class SaveBundleResult(BaseModel):
    """Result of save_session_bundle batch tool."""
    session: SessionResult
    tracking: TrackingResult | None
    project_ref: ProjectRefResult | None
    jsonl_session_ids: list[str] | None = None


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


class TurnCommand(BaseModel):
    """A command executed during a turn."""
    command: str  # truncated to 200 chars
    status: str = "success"  # "success" | "error"


class ConversationTurn(BaseModel):
    """A single user→assistant conversation turn."""
    timestamp: str
    user_prompt: str
    tools_used: list[str]
    response_summary: str
    tokens: TurnTokens | None = None
    context_window: int = 0  # prompt size of last API call (input + cache_read + cache_creation)
    subagent_tokens: TurnTokens | None = None
    commands: list[TurnCommand] = []
    files_modified: list[str] = []


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
    total_tokens: int  # input + output + cache_creation (excludes cache_read)
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int  # per-call (not cumulative across turns)
    cache_creation_tokens: int
    subagent_input_tokens: int = 0
    subagent_output_tokens: int = 0
    subagent_cache_creation_tokens: int = 0
    tools_summary: dict[str, int]
    files_read: list[str]
    files_written: list[str]
    commands_run: list[str]

    def to_summary(self) -> "ClaudeSessionSummary":
        """Convert to a trimmed summary for batch reads."""
        return ClaudeSessionSummary(
            session_id=self.session_id,
            project_name=self.project_name,
            git_branch=self.git_branch,
            model=self.model,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_minutes=self.duration_minutes,
            conversation=self.conversation,
            total_user_messages=self.total_user_messages,
            total_assistant_messages=self.total_assistant_messages,
            total_tool_calls=self.total_tool_calls,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_creation_tokens=self.cache_creation_tokens,
            subagent_input_tokens=self.subagent_input_tokens,
            subagent_output_tokens=self.subagent_output_tokens,
            tools_summary=self.tools_summary,
        )


class ClaudeSessionSummary(BaseModel):
    """Trimmed session for batch reads — drops heavy fields like files_read, commands_run."""
    session_id: str
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
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    subagent_input_tokens: int = 0
    subagent_output_tokens: int = 0
    tools_summary: dict[str, int]


class ClaudeSessionsBatchResult(BaseModel):
    """Result of batch reading multiple Claude sessions."""
    sessions: list[ClaudeSessionSummary]
    count: int


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
