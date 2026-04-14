---
name: codex-session-memory
description: Use when work spans multiple sessions and you need durable local memory for decisions, bug trails, and handoff context. Provides a Codex-native capture and retrieval workflow (search -> timeline -> get) without Claude plugin hooks.
---

# Codex Session Memory

Codex cannot rely on Claude-specific lifecycle hooks, so this skill uses explicit checkpoints and a local SQLite memory store.

## When to Use

- Multi-session bugfixing, refactors, migration work, and incident response
- You need to preserve why a decision was made, not just what changed
- You want fast recall without reading full git history

## Core Workflow

1. Capture at key moments with `add` or `checkpoint`
2. Recall with token-efficient 3-step flow:
   - `search` for compact index
   - `timeline` for nearby context
   - `get` for full details of selected IDs
3. Continue work, then write a final handoff checkpoint

## Commands

Initialize memory DB (optional; auto-created on first write):

```bash
python .agents/skills/codex-session-memory/scripts/mem.py init
```

Capture explicit note:

```bash
python .agents/skills/codex-session-memory/scripts/mem.py add \
  --type decision \
  --summary "Use control API fallback for actor profile enrichment" \
  --details "Cloud endpoint flaky in staging; fallback keeps profile data stable." \
  --tags auth,control-api,fallback \
  --files src/hooks/use-cloud-auth.ts
```

Capture checkpoint from current repo state:

```bash
python .agents/skills/codex-session-memory/scripts/mem.py checkpoint \
  --summary "After lint fix pass" \
  --why "Track what changed before next auth refactor"
```

Recall (progressive disclosure):

```bash
python .agents/skills/codex-session-memory/scripts/mem.py search "auth fallback"
python .agents/skills/codex-session-memory/scripts/mem.py timeline --id 12 --window 2
python .agents/skills/codex-session-memory/scripts/mem.py get --ids 10,12,13
```

## Capture Rules

- Use short summaries (one sentence, outcome-first)
- Put rationale in `details`
- Add tags for subsystem and intent (e.g. `auth`, `ui`, `risk`, `rollback`)
- Include touched files for faster follow-up

## Retrieval Rules

- Do not fetch full details for every result
- Always filter with `search` first, then `timeline`, then `get`
- When responding to users, cite memory IDs when relevant

## Storage

- Default DB path: `.agents/skills/codex-session-memory/data/memory.db`
- Override with `--db <path>` for per-project/per-branch storage

