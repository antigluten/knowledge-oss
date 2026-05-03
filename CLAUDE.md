# Claude Code Instructions — Knowledge Vault

## Memory: Read at Session Start

At the start of every session in this directory, silently read:

**Static memory (identity + preferences — rarely change):**
- `memory/user.md` — who you are, background, expertise
- `memory/preferences.md` — how you like to work, code style, process preferences
- `memory/decisions.md` — key architecture decisions across projects
- `memory/people.md` — people and teams mentioned

**Live state (change often — always read these):**
- `memory/current.md` — current projects, priorities, blockers
- `memory/future.md` — upcoming events, plans, ideas, arrangements
- The most recent file in `memory/daily/` (previous day or two)

Also skim the tail of `log.md` (last ~20 entries) to understand recent vault activity:

```bash
grep "^## \[" log.md | tail -20
ls -t memory/daily/ | head -3
```

## Log.md — Append-Only Timeline

`log.md` records meaningful operations. Append one entry per ingest, synthesis, or
lint pass:

```
## [YYYY-MM-DD] <event> | <title>

<1-3 line context>
```

Events: `ingest`, `synthesis`, `query`, `lint`, `meta`. Skip trivial chats.

## Filing Chat Query Results

When a conversation produces a substantive synthesized answer (comparison, analysis,
cross-note connection), offer to file it as `synthesis--<slug>.md` with
`source: claude-session` and `related:` listing drawn-from notes.

## Memory: Update During and At End of Session

**During the session — append to the daily log:**

Every meaningful decision or context shift gets an entry in today's daily log at
`memory/daily/YYYY-MM-DD.md`. Create the file if it doesn't exist. Format:

```
## HH:MM — <headline>

<1-3 line body>
```

Append in chronological order, newest at the bottom.

**At session end — update the live state files if anything changed:**

- `memory/current.md` — if projects/priorities/blockers shifted
- `memory/future.md` — add dated entries; move completed items to today's daily log

**At session end — update static memory only for durable new facts:**

- New tools, workflows, or preferences observed → `memory/preferences.md`
- New architecture decisions made → `memory/decisions.md`
- New people or project context → `memory/people.md`
- Updates to your role or expertise → `memory/user.md`

**Rules for static memory updates:**
- Only add genuinely new, durable facts — not session-specific details
- Do not repeat information already present
- Keep files concise — delete outdated info when replacing it

## Project Context

This is a flat Obsidian knowledge vault that doubles as persistent LLM memory.

**Key scripts (run from this directory):**
- `python3 rebuild_index.py` — regenerate all MOC files and `glossary.md`
- `python3 ingest_sources.py perplexity` — batch-ingest new Perplexity exports
- `python3 ingest_sources.py claude-session list|mark` — track Claude session ingests
- `python3 link_notes.py .` — LLM-based semantic cross-linker (needs `ANTHROPIC_API_KEY`)

**Key files:**
- `log.md` — append-only chronological record of vault operations
- `memory/current.md` — live state snapshot
- `memory/future.md` — upcoming events, plans, ideas
- `memory/daily/` — timestamped daily logs
- `moc--master-index.md` — top-level catalog (regenerated)
- `glossary.md` — A–Z term index (regenerated — never hand-edit)

**Optional dual-vault add-on:**
If you want to split technical and personal contexts across two vaults
(with cross-routing, authorship markers, and a copy-edit pipeline), see
`docs/dual-vault-pattern.md`.
