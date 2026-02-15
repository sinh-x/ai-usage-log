"""Initial content templates for tracking files."""

LEARNING_QUEUE = """\
# Learning Queue

Topics and skills to explore, prioritized by interest and relevance.

## High Priority

## Medium Priority

## Backlog

## Completed
"""

SKILLS_GAINED = """\
# Skills Gained

Knowledge and capabilities acquired through AI-assisted learning.

## By Category

### Programming

### DevOps

### Tools

### Concepts

## By Date

| Date | Skill | Source Session |
|------|-------|----------------|
"""

STATISTICS = """\
# AI Usage Statistics

## Lifetime Totals
- Total sessions: 0
- Total time: 0 hours
- Sessions by agent: {}

## By Month
| Month | Sessions | Hours | Top Agent | Top Topic |
|-------|----------|-------|-----------|-----------|

## By Agent
| Agent | Sessions | Avg Duration | Top Topics |
|-------|----------|--------------|------------|
"""

VERIFICATION_QUEUE = """\
# Verification Queue

Claims and facts from AI sessions that need independent verification.

## Pending Verification

| Date | Claim | Source Session | Verify Via | Priority |
|------|-------|----------------|------------|----------|

## In Progress

## Verified (Correct)

| Date | Claim | Verified Via | Notes |
|------|-------|--------------|-------|

## Verified (Incorrect/Partial)

| Date | Original Claim | Actual Truth | Source |
|------|----------------|--------------|--------|

## Verification Methods
- **Official Docs**: MDN, man pages, language specs, RFCs
- **Test**: Run in isolated environment, container, or VM
- **Multiple Sources**: Cross-reference 2-3 authoritative sources
- **Community**: Stack Overflow consensus, GitHub issues
"""

QUIZ_BANK = """\
# Quiz Bank

Self-test questions generated from AI sessions. Use for spaced repetition.

## How to Use
1. Cover the answer (between ||spoiler tags||)
2. Try to answer from memory
3. Check and rate: Easy / Medium / Hard / Failed
4. Review failed items more frequently

## By Topic

### Programming

### DevOps

### Tools & Commands

### Concepts

## Recent Additions

| Date | Question | Topic | Difficulty |
|------|----------|-------|------------|

## Review Schedule
- Daily: Items marked "Failed" or "Hard"
- Weekly: Items marked "Medium"
- Monthly: All items (refresh)
"""

# Map of filename -> template content
TRACKING_FILES: dict[str, str] = {
    "learning-queue.md": LEARNING_QUEUE,
    "skills-gained.md": SKILLS_GAINED,
    "statistics.md": STATISTICS,
    "verification-queue.md": VERIFICATION_QUEUE,
    "quiz-bank.md": QUIZ_BANK,
}
