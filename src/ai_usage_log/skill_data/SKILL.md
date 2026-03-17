---
name: ai-usage-log
description: Creates structured session summaries documenting AI interactions, learnings, and growth areas. Portable across AI agents (Claude Code, ChatGPT, Cursor, etc.) for unified tracking of your AI-assisted learning journey. This skill should be used when the user wants to log a session, says "log this session", uses /ai-usage-log, or indicates they are ending a session.
---

# AI Usage Log

Cross-platform skill for documenting AI sessions, tracking learnings, and identifying growth areas. Works with any AI agent that can read markdown. **MCP Backend**: all file I/O is delegated to the `ai-usage-log` MCP server — the agent focuses on content generation.

## Quick Reference

### Standard Flow (3 MCP calls, 1 user interaction)

```
Step 0  prepare_session(cwd, cache_path) → slim response + full JSON at cache_path
        ↳ Use jq to read previous_session, stats, computed_stats, timeline from cache_path
Step 1  (no MCP) Tier Selection          → pick Tier 1/2/3
Step 2  (no MCP) Session Reflection      → 2-round recall + agent feedback (only user interaction)
Step 3  get_daily_jsonl_stats(today, cache_path=...) → slim + full stats at cache_path
        ↳ Use jq to extract token totals, tools histogram, per-session data
Step 4  (no MCP) Generate markdown       → assemble content with JSONL stats in Key Stats
Step 5  (no MCP) Show generated content  → display rendered markdown to user
Step 6  save_session_bundle(content=...) → auto-save immediately after display (no confirmation)
        ↳ MUST: update_session if Session ID still shows "pending"
Step 7  (no MCP) Show result summary     → saved path, quick stats, key takeaways
```

#### Large-Response Tool Cache Pattern

All 5 large-response tools support `cache_path`:
- `prepare_session(cwd, cache_path=...)` — full PrepareSessionResult
- `read_claude_session(session_id, cache_path=...)` — full ClaudeSessionData
- `read_claude_sessions(session_ids, cache_path=...)` — full ClaudeSessionsBatchResult
- `get_session_timeline(session_id, cache_path=...)` — full SessionTimeline
- `get_daily_jsonl_stats(date, cache_path=...)` — full DailyAggregate

If `cache_path` is omitted, auto-saves to `/tmp/ai-usage-log/<tool>-<timestamp>.json`.
Always returns slim response. Always use `jq` to extract what you need.

### Tier Selection Cheat Sheet

| Signal    | Tier 1 (Quick)   | Tier 2 (Standard)   | Tier 3 (Deep)              |
| --------- | ---------------- | -------------------- | -------------------------- |
| Duration  | <20 min          | 20–90 min            | >90 min or multi-context   |
| Messages  | <8               | 8–25                 | >25                        |
| Depth     | Routine/mechanical | Some new concepts  | Significant learning       |

Pick the tier matching the **highest** signal. When in doubt, go one tier up.

### Section Checklist

| Section               | Tier 1          | Tier 2          | Tier 3          |
| --------------------- | --------------- | --------------- | --------------- |
| Header block          | MUST (compact)  | MUST (standard) | MUST (standard) |
| Update History        | NO              | MUST            | MUST            |
| Session Flow (mermaid)| NO              | MUST            | MUST            |
| Timeline              | MUST (3–5 items)| MUST (full)     | MUST (full)     |
| Key Stats             | MAY (inline)    | MUST (table)    | MUST (table)    |
| What I Learned        | MUST (flat list)| MUST (Tech+Process) | MUST (Tech+Process+Tools+opt) |
| Areas to Improve      | NO              | MAY             | MUST (3 tiers)  |
| Session Quality       | NO              | MUST            | MUST            |
| My Reflections        | NO              | MUST            | MUST            |
| Verification Queue    | NO              | MAY (if claims) | MUST (if claims)|
| Follow-up Tasks       | MUST            | MUST            | MUST            |
| Tags                  | MUST            | MUST            | MUST            |

## Installation

### Prerequisites

Install and configure the `ai-usage-log` MCP server. See the [main README](../../README.md) for setup.

### Install Skill

Copy this skill directory to your Claude Code skills location:

```bash
cp -r skill/ai-usage-log ~/.claude/skills/ai-usage-log
```

The skill is auto-detected by Claude Code when the `ai-usage-log` MCP server is configured.

### Configuration

Set the log output directory via environment variable (default: `~/Documents/ai-usage`):

```bash
export AI_USAGE_LOG_PATH=~/Documents/ai-usage
```

## Session Logging (Steps 0–7)

### Step 0: Prepare Session (1 MCP call)

Call `prepare_session(cwd=<current_working_directory>, cache_path=<your_workspace>/session-cache.json)`.

**All large-response tools now use a slim cache pattern.** Full JSON is written to `cache_path` (or auto-generated under `/tmp/ai-usage-log/` if omitted). The tool always returns a slim response — use `jq` to extract specific fields on demand.

#### Slim response fields (always inline):
- `cached_at`: path to the full JSON cache file
- `schema_paths`: flat list of available jq paths with size hints
- `context`: core metadata `{user, host, terminal, cwd, project, project_root, date, time, year, month}` — inline, always small
- `message`: reminder to use jq

#### Extracting data from the cache:

```bash
# Get context inline from slim response — no jq needed
# context.date, context.user, context.project, context.cwd are always inline

# Read previous session content
jq -r '.previous_session.content' <cache_path>

# Get stats file content
jq -r '.stats.content' <cache_path>

# Get computed stats summary
jq '.computed_stats.total_sessions, .computed_stats.by_agent' <cache_path>

# Get session timeline entries
jq '.current_session_timeline.entries' <cache_path>
```

Store `cached_at` from the slim response — it's the path to use for all jq extractions.
**`current_session_timeline` is the primary source for Timeline timestamps** — use its entries instead of fabricating times.

If `previous_session` exists and has open todos, present to user:

```markdown
## Previous Session: `abc123` (2026-02-08)

**Open Todos:**
- [ ] Add error handling for edge cases
- [ ] Write unit tests

**Options:**
1. **Carry forward** - Continue with these todos
2. **Start fresh** - Begin without carrying items
3. **Select items** - Choose specific items
```

### Step 1: Tier Selection (no MCP)

Evaluate the session against the tier signals and pick the **highest matching tier**.

Rules:
- Pick highest signal (e.g., 15 min but deep learning → Tier 3)
- Multi-context sessions (resumed, multiple topics) → always Tier 3
- When in doubt, go one tier up

Announce the tier to the user: "This looks like a **Tier N** session — I'll use the [Quick/Standard/Deep] template."

### Step 2: Session Reflection (no MCP)

Before generating the log, run a quick **retrieval practice** exercise.

- **Tier 1**: Skip reflection entirely. Proceed to Step 3.
- **Tier 2/3**: Run the two-round flow below.

> **Shortcut**: User can say "skip reflection" to go directly to Step 3.

#### Round 1: Category Selection

**Use `AskUserQuestion`** — broad categories, user picks what applies:

```
AskUserQuestion(questions=[
  {
    question: "What did you accomplish this session? (from memory)",
    header: "Recall",
    options: [
      { label: "Built/shipped", description: "Code, feature, PR, deployment" },
      { label: "Fixed/debugged", description: "Bug, config issue, incident" },
      { label: "Planned/designed", description: "Architecture, spec, exploration" },
      { label: "Learned/researched", description: "New concept, tool, technique" }
    ],
    multiSelect: true
  },
  {
    question: "What was most valuable — or what mistake/surprise stood out?",
    header: "Highlight",
    options: [
      { label: "Key insight", description: "Something clicked or became clear" },
      { label: "Caught a mistake", description: "Error, wrong assumption, near-miss" },
      { label: "Unexpected result", description: "Something I didn't anticipate" },
      { label: "Nothing notable", description: "Routine session, no standout moment" }
    ],
    multiSelect: true
  },
  {
    question: "One thing to carry forward or do differently next time?",
    header: "Forward",
    options: [
      { label: "Reuse a pattern", description: "Technique or approach worth repeating" },
      { label: "Avoid a pitfall", description: "Something to watch out for" },
      { label: "Prioritize a todo", description: "Unfinished work that matters most" },
      { label: "Nothing specific", description: "No strong carry-forward this session" }
    ],
    multiSelect: true
  }
])
```

#### Round 2: Detail Expansion

For each selected category, ask a **focused follow-up** with options pre-populated from the actual conversation. Maximum 4 questions per `AskUserQuestion` call.

| Round 1 Category   | Round 2 Question              | Pre-populate from                        |
| ------------------ | ----------------------------- | ---------------------------------------- |
| Built/shipped      | "What did you build or ship?" | PRs, new files, features discussed       |
| Fixed/debugged     | "What did you fix or debug?"  | Errors, bug discussions, config fixes    |
| Planned/designed   | "What did you plan or design?"| Architecture discussions, specs, diagrams |
| Learned/researched | "What did you learn?"         | New concepts, tools, commands used       |
| Key insight        | "Which insight stood out?"    | Aha moments, things that clicked         |
| Caught a mistake   | "What mistake did you catch?" | Errors, wrong assumptions, corrections   |
| Unexpected result  | "What was unexpected?"        | Surprises, deviations from plan          |
| Reuse a pattern    | "Which pattern to reuse?"     | Techniques, workflows worth repeating    |
| Avoid a pitfall    | "What pitfall to avoid?"      | Footguns, time sinks, false starts       |
| Prioritize a todo  | "Which todo matters most?"    | Open items from session                  |

> Skip categories with "Nothing notable" / "Nothing specific". If Round 2 would have only 1 question with 1 obvious option, skip it and use that item directly.

#### After Both Rounds

Compare user's recall against actual conversation:
- **Confirm** what they remembered correctly
- **Surface** anything significant they forgot
- **Gently correct** any misremembered details

Fold user's own words into `## My Reflections`. Round 1 categories become structure; Round 2 details become content.

### Step 3: Fetch JSONL Stats (1 MCP call)

Call `get_daily_jsonl_stats(date=<today>, project_path=<cwd>)` to get aggregated stats for the current project.

The result includes **per-session details** with `session_id`, `git_branch`, `start_time`, `end_time`, `tools_summary`. A single user work session may span multiple JSONL sessions (context resets, resumed conversations). The agent decides which to include based on:
- **Git branch** — same branch = likely same work session
- **Timestamps** — sessions close together (e.g., within a few hours)
- **Topic continuity** — same project + related work

From the stats, extract for Key Stats:
- `total_tool_calls`, `total_user_messages`, `total_assistant_messages`
- `tools_histogram` (top tools used)
- `total_duration_minutes`
- `model_distribution`
- Per-session breakdown if multiple sessions contributed

> **Fallback**: If `get_daily_jsonl_stats` returns no data, use `prepare_session`'s `current_session_timeline` for basic stats. If neither available, populate Key Stats from conversation memory only.

### Step 4: Generate Markdown (no MCP)

1. Select the tier template from [Session Templates](#session-templates) below
2. Fill in sections per the tier's section checklist
3. Include JSONL stats from Step 3 in the **Key Stats** table
4. Auto-pick the `agent` name: `repo-name-main-theme` kebab-case, max ~4 words (e.g., `anytype-mcp-security-audit`)
5. Assemble the full markdown content in memory

### Step 5: Show Generated Content (no MCP)

Display the full session log as **rendered markdown** to the user. This is informational — the save follows immediately without waiting for approval.

### Step 6: Auto-Save (1 MCP call)

**Immediately after displaying content**, call `save_session_bundle`:

```
save_session_bundle(year, month, date, agent,
    content=<markdown>,
    tracking_updates, project_root, user, host, project_ref_content,
    jsonl_session_ids=[...])
```

MCP handles file location, naming, and all writes. Returns `{session: {path, hash, filename, is_new}, tracking, project_ref}`. Store `session.hash` as `SESSION_HASH`.

**Session ID Fix** (MUST): If the markdown contained `Session ID: pending`, call:

```
update_session(session_hash=SESSION_HASH, content=<markdown with real hash>, year, month)
```

> **Why no confirmation gate?** The reflection in Step 2 already captures user intent. The user sees the content in Step 5 and the save is immediate. Edits can be requested afterward via `update_session`.

> **Large content fallback**: If content is too large for inline, write to `/tmp/ai-session-<hash>.md` and use `content_path` instead. MCP accepts either.

### Step 7: Show Result Summary (no MCP)

After save completes, show a concise summary:

```markdown
Session saved: `~/Documents/ai-usage/sessions/2026/02/2026-02-15-abc123-project-main-topic.md`

**~45 min** | Main topic | N learnings | N follow-ups

Key takeaways:
1. Takeaway 1
2. Takeaway 2
3. Takeaway 3
```

> If the user wants edits after seeing this, they can ask and the agent calls `update_session`.

## Session Templates

### Header Rules (all tiers)

**MUST** follow this exact format — one field per line, no exceptions:

````markdown
# AI Session Log

> Date: YYYY-MM-DD HH:MM
> Agent: Claude Code (Opus X.Y)
> Duration: ~XX minutes
> Project: <description>
> Session ID: <6-char-hash>
> Updates: N
> User: <user>@<host>
> Working Directory: <path>
> Terminal Session: <mux:session>
````

Rules:
- Title is always `# AI Session Log` (never varies)
- One field per line in the blockquote
- 24h time format
- Duration is a single value (`~45 minutes`), never a range
- Session ID: use actual hash from `save_session_bundle`, never "pending"

### Tier 1 Template (Quick)

For sessions <20 min, <8 messages, or purely routine/mechanical work.

````markdown
# AI Session Log

> Date: YYYY-MM-DD HH:MM
> Agent: Claude Code (Opus X.Y)
> Duration: ~XX minutes
> Project: <description>
> Session ID: <6-char-hash>
> Updates: 0
> User: <user>@<host>
> Working Directory: <path>
> Terminal Session: <mux:session>

---

## Timeline

1. **HH:MM** - Action 1
2. **HH:MM** - Action 2
3. **HH:MM** - Action 3

## What I Learned

- [ ] Learning 1
- [ ] Learning 2

## Follow-up Tasks

- [ ] Task 1
- [ ] **Verify**: Verification task

## Tags

#topic1 #topic2
````

Key Stats MAY appear inline: `**Stats**: 5 messages, 2 files modified, tools: Read, Edit`

### Tier 2 Template (Standard)

For sessions 20–90 min, 8–25 messages, or involving some new concepts.

````markdown
# AI Session Log

> Date: YYYY-MM-DD HH:MM
> Agent: Claude Code (Opus X.Y)
> Duration: ~XX minutes
> Project: <description>
> Session ID: <6-char-hash>
> Updates: N
> User: <user>@<host>
> Working Directory: <path>
> Terminal Session: <mux:session>

## Update History

| # | Time  | Summary                     |
| - | ----- | --------------------------- |
| 0 | HH:MM | Initial session log created |

---

## Session Flow

```mermaid
graph LR
    A[Goal] --> B[Step 1]
    B --> C[Step 2]
    C --> D[Outcome]
```

## Timeline

1. **HH:MM** - Started with goal X
2. **HH:MM** - Discussed options
3. **HH:MM** - Implemented solution
4. **HH:MM** - Verified results

## Key Stats

| Metric                 | Value               |
| ---------------------- | ------------------- |
| Messages exchanged     | N                   |
| Files created/modified | N                   |
| Tools used             | Read, Edit, Bash    |
| Tool calls             | N                   |
| Model                  | claude-opus-X-Y     |
| Primary topic          | Topic / Category    |

## What I Learned

### Technical

- [ ] Learning item 1
- [ ] Learning item 2

### Process

- [ ] Process insight 1

## Session Quality

- **Productivity**: N/5 - Description
- **Learning**: N/5 - Description
- **Clarity**: N/5 - Description
- **Efficiency**: N/5 - Description

## My Reflections

> *Captured from retrieval practice at session end.*

**What I recalled:** (user's free recall of accomplishments)

**Most valuable / surprise:** (user's own words)

**Carry forward:** (user's forward-looking note)

**Agent feedback:** (what the agent confirmed, surfaced, or corrected)

## Follow-up Tasks

- [ ] Task 1
- [ ] **Verify**: Verification task
- [ ] **Search**: Research task

## Tags

#topic1 #topic2 #topic3
````

**MAY include** (if applicable): Areas to Improve, Verification Queue.

### Tier 3 Template (Deep)

For sessions >90 min, >25 messages, multi-context, or significant learning.

````markdown
# AI Session Log

> Date: YYYY-MM-DD HH:MM
> Agent: Claude Code (Opus X.Y)
> Duration: ~XX minutes
> Project: <description>
> Session ID: <6-char-hash>
> Updates: N
> User: <user>@<host>
> Working Directory: <path>
> Terminal Session: <mux:session>

## Update History

| # | Time  | Summary                     |
| - | ----- | --------------------------- |
| 0 | HH:MM | Initial session log created |

---

## Session Flow

```mermaid
graph LR
    A[Goal] --> B[Phase 1]
    B --> C[Phase 2]
    C --> D[Phase 3]
    D --> E[Outcome]
```

## Timeline

1. **HH:MM** - Started with goal X
2. **HH:MM** - Phase 1 details
3. **HH:MM** - Phase 2 details
4. **HH:MM** - Phase 3 details
5. **HH:MM** - Wrapped up

## Key Stats

| Metric                 | Value               |
| ---------------------- | ------------------- |
| Messages exchanged     | N                   |
| Files created/modified | N                   |
| Tools used             | Read, Edit, Bash    |
| Tool calls             | N                   |
| Model                  | claude-opus-X-Y     |
| Primary topic          | Topic / Category    |

## What I Learned

### Technical

- [ ] Learning item 1
- [ ] Learning item 2

### Process

- [ ] Process insight 1

### Tools/Commands

- [ ] `command` - what it does

## Areas to Improve

### Immediate (This Week)

- [ ] Task 1

### Medium-term

- [ ] Task 2

### Long-term

- [ ] Task 3

## Session Quality

- **Productivity**: N/5 - Description
- **Learning**: N/5 - Description
- **Clarity**: N/5 - Description
- **Efficiency**: N/5 - Description

## My Reflections

> *Captured from retrieval practice at session end.*

**What I recalled:** (user's free recall of accomplishments)

**Most valuable / surprise:** (user's own words)

**Carry forward:** (user's forward-looking note)

**Agent feedback:** (what the agent confirmed, surfaced, or corrected)

## Verification Queue

| Claim      | Confidence | Verify Via    | Status      |
| ---------- | ---------- | ------------- | ----------- |
| Claim text | Medium     | How to verify | [ ] Pending |

## Follow-up Tasks

- [ ] Task 1
- [ ] **Verify**: Verification task
- [ ] **Search**: Research task

## Tags

#topic1 #topic2 #topic3
````

## Session Continuity

### Update vs Create Logic

1. **First call in session**: Create new log with unique hash
2. **Subsequent calls**: Update existing log (append new content)

Track internally: `SESSION_HASH`, `SESSION_FILE`, `UPDATE_COUNT`.

When updating, mark new content with `[NEW]`:

```markdown
## What I Learned

### Technical

- [x] Tiered snapshot approach (original)
- [x] **[NEW]** Testing skills on real directories
- [x] **[NEW]** Bash error handling patterns
```

### Context-Aware Triggering

**Low Context Warning (15%)**: Notify, ask to log. **Critical (<5%)**: Skip showing content, save immediately.

**Goodbye/Exit**: Detect phrases like "bye", "done", "exit". Run Steps 0–7 automatically.

**Mid-Session Checkpoint**: User can call `/ai-usage-log` anytime to save progress.

**Project Context**: When in a git repo, save reference via `save_project_ref` in `save_session_bundle`.

## Daily Summary

When user requests `/ai-usage-log daily` or "daily summary":

1. Call `list_sessions(date=<target_date>)` to get all sessions for the day
2. Read each session file to extract done/todo items
3. Run a daily reflection (category selection + detail expansion, same two-round pattern)
4. Assemble daily summary content including reflection answers
5. Show assembled summary as rendered markdown
6. Call `create_daily_summary(year, month, date, content=<summary_markdown>)`

See [assets/daily-summary-template.md](assets/daily-summary-template.md) for the full daily template.

## Consistency Rules

### MUST (violation = broken log)

- Title is always `# AI Session Log`
- Header: one field per line in blockquote, 24h time, no duration ranges
- Session ID: actual 6-char hash, **never** "pending"
- After `save_session_bundle`, if Session ID is "pending", call `update_session` to fix
- Tier selection before generating content
- Follow section checklist for the selected tier
- Auto-save after showing content — no confirmation gate between display and save
- **Timestamps in Timeline MUST come from verifiable sources** — JSONL session data, tool call timestamps, or explicit user statements. **NEVER fabricate or guess timestamps.** If no timestamp data is available, use relative ordering (`Step 1`, `Step 2`) instead of clock times.

### SHOULD (strong recommendation)

- Use kebab-case brief for filename suffix (max ~4 words)
- Pre-populate Round 2 options from actual session data
- Include mermaid flow for Tier 2/3
- Mark new content with `[NEW]` on updates
- Include JSONL stats in Key Stats (Step 3)

### MAY (agent discretion)

- Include inline stats for Tier 1
- Add Quiz Questions for learning-heavy Tier 3 sessions
- Include Verification Queue for Tier 2 if unverified claims exist

## MCP Tool Reference

### Standard Flow Tools

| Tool                      | Purpose                                                          | Step   |
| ------------------------- | ---------------------------------------------------------------- | ------ |
| **`prepare_session`**     | Context + dirs + previous + stats + computed + timeline (6-in-1) | Step 0 |
| **`get_daily_jsonl_stats`** | Aggregate JSONL stats for date range                           | Step 3 |
| **`save_session_bundle`** | Create session + tracking + project ref + JSONL cache (4-in-1)   | Step 6 |
| `update_session`          | Update existing session by hash                                  | Step 6 |

### On-Demand Tools

| Tool                      | Purpose                                                     |
| ------------------------- | ----------------------------------------------------------- |
| `list_claude_sessions`    | Discover JSONL sessions from ~/.claude/projects/            |
| `read_claude_session`     | Parse full JSONL → structured data (single session)         |
| `read_claude_sessions`    | Batch-read multiple JSONL sessions → trimmed summaries      |
| `get_session_timeline`    | Lightweight timeline (timestamps + tools + files)           |
| `extract_session_stats`   | Parse JSONL + cache stats to statistics/ dir                |
| `compute_stats`           | Aggregate stats from session filenames (read-only)          |
| `list_sessions`           | List sessions by date/month/count                           |
| `create_daily_summary`    | Write daily summary file                                    |

### Legacy Tools (prefer batch equivalents)

| Tool                  | Replaced by         |
| --------------------- | ------------------- |
| `get_session_context` | prepare_session     |
| `init_structure`      | prepare_session     |
| `create_session`      | save_session_bundle |
| `get_previous_session`| prepare_session     |
| `save_project_ref`    | save_session_bundle |
| `update_tracking`     | save_session_bundle |
| `get_stats`           | prepare_session     |

## Reference

### Log Location

```
~/Documents/ai-usage/
├── sessions/YYYY/MM/YYYY-MM-DD-<hash>-<brief>.md
├── daily/YYYY/MM/YYYY-MM-DD-daily.md
├── insights/weekly/YYYY-WNN.md
├── insights/monthly/YYYY-MM.md
├── statistics/                                    # Cached JSONL stats
│   └── YYYY-MM-DD--<project>--<session-id>.json
├── learning-queue.md
├── skills-gained.md
├── verification-queue.md
├── quiz-bank.md
└── statistics.md
```

### Save Bundle Parameters

```
save_session_bundle(year, month, date, agent,
    content | content_path,          # one required; content_path for large logs
    tracking_updates,                # dict of filename → full content (optional)
    project_root, user, host,        # for project reference (optional)
    project_ref_content,
    jsonl_session_ids)               # list of JSONL session UUIDs to extract+cache (optional)
```

Returns `{session: {path, hash, filename, is_new}, tracking, project_ref, jsonl_session_ids}`.

### Tags Taxonomy

- **Topics**: #programming #devops #design #writing #research
- **Languages**: #python #bash #typescript #rust
- **Tools**: #git #docker #kubernetes #terraform
- **Skills**: #debugging #architecture #testing #automation
- **Meta**: #skill-development #learning #productivity
