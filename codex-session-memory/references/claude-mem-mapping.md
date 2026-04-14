# Claude-Mem to Codex Mapping

This note maps concepts from `thedotmack/claude-mem` to Codex-compatible mechanisms.

## Goals Preserved

- Durable memory across sessions
- Token-efficient retrieval
- Better continuity for long-running engineering work

## What Cannot Be Ported 1:1

- Claude plugin lifecycle hooks (`SessionStart`, `PostToolUse`, etc.)
- Claude-specific plugin runtime and worker service assumptions
- Automatic context injection at Claude session boundaries

## Codex-Native Substitutions

- Explicit checkpoint commands instead of hooks
- Local SQLite memory file inside repository
- Retrieval workflow kept as:
  1. `search` for compact index
  2. `timeline` for neighboring context
  3. `get` for full details only for selected IDs

## Tradeoffs

- Pros:
  - No external service required
  - Works in any repo with Python 3
  - Fully auditable local data
- Cons:
  - Requires manual checkpoint discipline
  - No automatic event capture unless future wrappers are added

## Suggested Operational Cadence

- At session start: run `search` on active subsystem
- Before major refactor step: run `checkpoint`
- After tests/lint pass: run `checkpoint`
- Before handoff: run `add --type handoff`

