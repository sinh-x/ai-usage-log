# Claude JSONL Session File Format

Reference for the raw `.jsonl` files stored in `~/.claude/projects/{project-name}/{session-uuid}.jsonl`.

## Message Types

Each line is a JSON object with a top-level `type` field.

| Type | Description | Typical Count |
|------|-------------|---------------|
| `user` | Human input and tool results | High |
| `assistant` | Claude's responses (streamed in chunks) | High |
| `progress` | Subagent (Task tool) messages | Highest when subagents used |
| `system` | System metadata (timing, config) | Low |
| `file-history-snapshot` | File state snapshots at specific points | Low |
| `queue-operation` | User input queue (typed-ahead input, slash commands) | Low |

## Type Hierarchy

```
Session JSONL
│
├── file-history-snapshot
│     Fields: messageId, snapshot.trackedFileBackups, isSnapshotUpdate
│     Tracks file backups at specific conversation points
│
├── system
│     Fields: durationMs, isMeta, gitBranch, cwd
│     Bookkeeping (turn timing, configuration)
│
├── queue-operation
│     Fields: operation (enqueue|popAll), content, sessionId
│     Captures typed-ahead input or slash commands
│     e.g. "/extra-usage" enqueued then popped
│
├── user
│   ├── Direct messages
│   │     parentUuid: null (first message) or points to prior assistant
│   │     .message.role = "user"
│   │     .message.content = "string"
│   │     isMeta: false
│   │
│   └── Tool results (internal)
│         parentUuid → the assistant that called the tool
│         .message.content = [{type: "tool_result", tool_use_id: "..."}]
│         isMeta: true
│         sourceToolUseID: links back to the tool_use block
│
├── assistant (streamed in chunks)
│   │  Each chunk shares the same .message.id but gets a NEW .uuid
│   │  Linked via parentUuid chain: chunk1 → chunk2 → chunk3
│   │  stop_reason: null (streaming) | "stop_sequence" (final)
│   │
│   │  Content blocks inside .message.content[]:
│   ├── text          — Prose responses
│   ├── tool_use      — Tool calls (id, name, input)
│   └── thinking      — Extended thinking blocks (with signature)
│
└── progress (subagent messages)
      Wraps nested conversation inside .data.message
      Fields: toolUseID, parentToolUseID, data.type, data.message.type
      .data.message.type = "user" | "assistant" (subagent's own turns)
      Forms its own parentUuid chain WITHIN the progress stream
```

## Common Fields

Fields present on most message types:

| Field | Description |
|-------|-------------|
| `uuid` | Unique identifier for this JSONL line |
| `parentUuid` | Points to previous message (forms linked list) |
| `type` | Top-level message type |
| `timestamp` | ISO 8601 timestamp |
| `sessionId` | Session UUID |
| `cwd` | Working directory at time of message |
| `gitBranch` | Active git branch |
| `version` | Claude Code version |
| `isSidechain` | `true` = subagent message, `false` = main thread |
| `isMeta` | `true` = internal (tool result), `false` = real user input |

## Assistant Message Fields

```jsonc
{
  "type": "assistant",
  "message": {
    "model": "claude-opus-4-6",
    "id": "msg_...",           // Same across streamed chunks
    "type": "message",
    "role": "assistant",
    "content": [
      // One of:
      {"type": "text", "text": "..."},
      {"type": "thinking", "thinking": "...", "signature": "..."},
      {"type": "tool_use", "id": "toolu_...", "name": "Read", "input": {...}}
    ],
    "stop_reason": null,       // null while streaming, "stop_sequence" at end
    "usage": {
      "input_tokens": 3,
      "output_tokens": 14,
      "cache_creation_input_tokens": 0,
      "cache_read_input_tokens": 0
    }
  },
  "requestId": "req_..."
}
```

## Key Relationships

- **`parentUuid` → `uuid`**: Forms the conversation linked list
- **`message.id`**: Groups streamed assistant chunks (same API response, multiple JSONL lines)
- **`sourceToolUseID`**: On `user` (isMeta=true) messages, links tool result back to the `tool_use` block
- **`toolUseID` / `parentToolUseID`**: On `progress` messages, links subagent back to parent Task call

## Useful jq Commands

```bash
# Count message types
jq -r '.type' session.jsonl | sort | uniq -c | sort -rn

# Extract conversation flow (type + role)
jq -r '[.type, .message.role // ""] | @tsv' session.jsonl

# Get only real user messages
jq -r 'select(.type == "user" and .isMeta != true) | .message.content' session.jsonl

# Get assistant text content
jq -r 'select(.type == "assistant") | .message.content[]? | select(.type == "text") | .text' session.jsonl

# List tool calls
jq -r 'select(.type == "assistant") | .message.content[]? | select(.type == "tool_use") | .name' session.jsonl | sort | uniq -c | sort -rn

# Get token usage per assistant message
jq -r 'select(.type == "assistant" and .message.usage.output_tokens > 0) | [.message.id, .message.usage.input_tokens, .message.usage.output_tokens] | @tsv' session.jsonl

# Main thread only (exclude subagent messages)
jq -r 'select(.isSidechain != true)' session.jsonl
```

## Subagent File Structure

```
~/.claude/projects/{project-name}/
  {session-uuid}.jsonl                  # Main agent
  {session-uuid}/
    agent_{agent-uuid}.jsonl            # Subagent 1
    agent_{agent-uuid}.jsonl            # Subagent 2

# Legacy structure (older sessions):
~/.claude/projects/{project-name}/
  {session-uuid}.jsonl                  # Main agent
  agent_{agent-uuid}.jsonl              # Subagent at project root
```
