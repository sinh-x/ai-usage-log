# Claude DevTools - Message Grouping & Display Reference

How [claude-devtools](../../) parses, classifies, and groups Claude JSONL session messages for visualization.

Source: `/home/sinh/git-repos/sinh-x/tools/claude-devtools/`

## 5-Category Classification System

Every parsed message is classified into one of five categories:

| # | Category | Renders As | Side |
|---|----------|------------|------|
| 1 | **USER** | User speech bubble | Right |
| 2 | **SYSTEM** | Command output block | Left (gray) |
| 3 | **HARD NOISE** | Hidden (filtered out) | - |
| 4 | **COMPACT** | Boundary marker | Center |
| 5 | **AI** | AI response bubble | Left |

### Category 1: USER

**Criteria:**
- `type: 'user'`
- `isMeta != true`
- Contains text/image content
- Does NOT start with: `<local-command-stdout>`, `<local-command-caveat>`, `<system-reminder>`

### Category 2: SYSTEM

**Criteria:**
- `type: 'user'` (command output is stored as user entry)
- Content starts with `<local-command-stdout>` tag

### Category 3: HARD NOISE (filtered out)

**Criteria:**
- Entry types: `system`, `summary`, `file-history-snapshot`, `queue-operation`
- User messages with ONLY `<local-command-caveat>` or `<system-reminder>`
- Assistant messages with `model='<synthetic>'`
- Messages with `parentUuid: null` (orphaned root messages)

### Category 4: COMPACT

**Criteria:**
- `isCompactSummary: true`
- Marks where conversation context was compacted

### Category 5: AI (buffered)

**Criteria:**
- All remaining messages
- Includes: assistant messages, tool results, user interruptions
- Consecutive AI messages are grouped into ONE AIChunk

## Chunk Building Algorithm

AI chunks are **independent** - consecutive AI messages buffer into a single chunk:

```
aiBuffer = []

for each message:
  if hardNoise  → skip
  if user       → flush aiBuffer → AIChunk, create UserChunk
  if system     → flush aiBuffer → AIChunk, create SystemChunk
  if compact    → flush aiBuffer → AIChunk, create CompactChunk
  if ai         → aiBuffer.push(message)

flush remaining aiBuffer → AIChunk
```

Streamed assistant chunks (same `message.id`, multiple `uuid`s) plus their tool results all merge into **one AIChunk**.

## Key Fields for Grouping

| Field | Purpose |
|-------|---------|
| `isMeta` | `true` = internal (tool result), `false` = real user input |
| `isSidechain` | `true` = subagent message, filter from main thread |
| `sourceToolUseID` | Links tool result back to its `tool_use` call |
| `parentUuid` → `uuid` | Conversation threading chain |
| `message.id` | Groups streamed assistant chunks (same API response) |

## Type Processing Pipeline

```
ChatHistoryEntry (raw JSONL line)
  ↓ parseJsonlLine()
ParsedMessage (enriched with toolCalls[], toolResults[])
  ↓ MessageClassifier.categorizeMessage()
ClassifiedMessage (category: user|system|hardNoise|ai|compact)
  ↓ ChunkBuilder.buildChunks()
EnhancedChunk (visualization-ready)
  ├── EnhancedUserChunk
  ├── EnhancedAIChunk
  │     ├── responses: ParsedMessage[]
  │     ├── toolExecutions: ToolExecution[]
  │     ├── processes: Process[] (linked subagents)
  │     └── semanticSteps: SemanticStep[]
  ├── EnhancedSystemChunk
  └── EnhancedCompactChunk
```

## Tool Execution Linking

Two-pass matching strategy:

**Pass 1:** Build map of `tool_use_id` → `{ToolCall, startTime}` from all assistant messages.

**Pass 2a (primary):** Match via `sourceToolUseID` field on internal user messages.

**Pass 2b (fallback):** Match via `toolResults[]` array content blocks.

Result: `ToolExecution` with `startTime`, `endTime`, `durationMs`.

## Subagent Linking

Two-tier strategy:

**Tier 1 (primary):** Match `subagent.parentTaskId` to Task `tool_use` block ID in the chunk.

**Tier 2 (fallback):** If no `parentTaskId`, match by time range overlap (subagent start/end within chunk start/end).

## Semantic Steps

From AIChunk responses, micro-steps are extracted:

| Step Type | Source |
|-----------|--------|
| `thinking` | Extended thinking content blocks |
| `tool_call` | Tool use blocks |
| `tool_result` | Tool result blocks |
| `subagent` | Linked subagent processes |
| `output` | Final text output |
| `interruption` | User interruption within AI turn |

Task `tool_use` blocks are filtered when corresponding subagents exist (avoids duplication).

## Conversation Groups (Alternative Grouping)

A simpler grouping used in some views - groups one user message with ALL responses until next user message:

```typescript
interface ConversationGroup {
  userMessage: ParsedMessage;       // Real user input
  aiResponses: ParsedMessage[];     // All AI messages until next user
  processes: Process[];             // Spawned subagents
  toolExecutions: ToolExecution[];  // Regular tool calls
  taskExecutions: TaskExecution[];  // Task calls with subagent linkage
}
```

## Key Source Files

| File | Purpose |
|------|---------|
| `src/main/types/jsonl.ts` | JSONL entry type definitions |
| `src/main/types/messages.ts` | ParsedMessage and classification types |
| `src/main/types/chunks.ts` | Chunk, Process, SemanticStep types |
| `src/main/utils/jsonl.ts` | Streaming JSONL parser |
| `src/main/services/parsing/SessionParser.ts` | Session parsing orchestration |
| `src/main/services/parsing/MessageClassifier.ts` | 5-category classification |
| `src/main/services/analysis/ChunkBuilder.ts` | Chunk building pipeline |
| `src/main/services/analysis/ToolExecutionBuilder.ts` | Tool execution tracking |
| `src/main/services/analysis/ProcessLinker.ts` | Subagent-to-chunk linking |
| `src/main/services/analysis/ConversationGroupBuilder.ts` | Alternative grouping |
| `src/main/utils/toolExtraction.ts` | Tool call/result extraction |
| `src/main/constants/messageTags.ts` | XML tag constants for filtering |
