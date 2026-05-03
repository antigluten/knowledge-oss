# knowledge-oss

A flat Obsidian vault that doubles as persistent LLM memory: ingest Claude /
Perplexity sessions, auto-index, semantic-link, and query from any project.

## What this is

A starter kit for keeping a personal knowledge vault that an LLM agent can
read, write, and search. The vault is plain markdown in a flat directory,
indexed by filename prefix and Obsidian wikilinks. Three Python scripts
handle ingest, indexing, and semantic cross-linking. A `memory/` directory
gives the agent durable identity, preferences, and project state across
sessions. A `CLAUDE.md` file tells the agent how to use it all.

## What it gives you

- **Vault scripts** — `ingest_sources.py`, `rebuild_index.py`, `link_notes.py`
- **Memory layout** — `memory/{user,preferences,decisions,people,current,future}.md`
  + `memory/daily/`
- **Manifest tracking** — `.manifests/` (git-tracked) records which raw
  sources have been ingested
- **Append-only log** — `log.md` is the changelog of vault operations
- **Session instructions** — `CLAUDE.md` tells Claude Code how to use the
  vault from this directory

## Quickstart

```bash
# 1. Clone where you want your vault to live
git clone https://github.com/antigluten/knowledge-oss.git ~/knowledge

# 2. Open it in Obsidian (optional but recommended)
#    File → Open vault → ~/knowledge

# 3. Start a Claude Code session in the vault
cd ~/knowledge
claude

# 4. Tell Claude about you: edit memory/user.md, memory/preferences.md
#    (or just chat — Claude will offer to update these as it learns)

# 5. Generate the empty index
python3 rebuild_index.py
```

To start ingesting sources:

```bash
mkdir -p ~/raw-sources/perplexity ~/raw-sources/claude-sessions
# drop a .md export into ~/raw-sources/perplexity/ and run:
python3 ingest_sources.py --vault . --source-dir ~/raw-sources perplexity
```

To run the semantic linker (requires `ANTHROPIC_API_KEY`):

```bash
export ANTHROPIC_API_KEY=...
python3 link_notes.py .
```

## How it works

The daily loop is:

```
sources → ingest → vault → query → synthesis → vault → lint → (repeat)
```

- **Ingest:** raw markdown (Perplexity exports, Claude conversation logs)
  becomes one or more cleaned notes in the vault. Manifests track what
  has been processed so re-runs are idempotent.
- **Index:** `rebuild_index.py` walks the vault, regenerates per-domain
  MOCs (Maps of Content) and the alphabetical glossary from frontmatter
  + the `> **TL;DR:** …` line in each note.
- **Query:** Claude reads the vault from inside the directory — index
  files, grep, and full-text search are all available.
- **Synthesize:** when a session produces a useful cross-note answer,
  Claude files it as `synthesis--<slug>.md` so future sessions can
  rediscover it.
- **Lint:** an occasional sweep for orphaned notes, broken links, and
  stale drafts.

## Vault prefixes

Notes are flat files; their filename prefix declares the kind of note:

| Prefix             | Purpose                              |
|--------------------|--------------------------------------|
| `concept--`        | atomic knowledge note                |
| `arch-decision--`  | ADR-style decision                   |
| `arch-pattern--`   | reusable architectural pattern       |
| `arch-system--`    | system overview                      |
| `bug-issue--`      | specific bug + fix                   |
| `bug-pattern--`    | recurring bug pattern                |
| `dev-snippet--`    | code snippet                         |
| `dev-workflow--`   | workflow / procedure                 |
| `dev-config--`     | configuration note                   |
| `tool--`           | tool documentation                   |
| `synthesis--`      | filed query / cross-note synthesis   |
| `moc--`            | Map of Content (regenerated)         |

## Customizing

See `docs/customizing.md` for the customization knobs: vault path,
raw-source path, LLM model, prefix taxonomy, manifest format, memory
layout, and the daily-log format.

## Optional: dual-vault pattern

A separate `docs/dual-vault-pattern.md` describes the dual-vault add-on:
one vault for technical context, one for personal, with automatic
cross-routing and an authored-by-Claude marker for ingested notes.
Adopt it if a single vault feels mixed.

## Setup guides

- `docs/setup-llm-wiki-en.md` — long-form English setup walkthrough
- `docs/setup-llm-wiki-ru.md` — Russian-language version
- `docs/migrating-external-vault.md` — how to fold an existing vault or
  journal into this layout

## Credits

Based on the author's working knowledge vault. Public release as a
starter kit so others can run the same pattern.

## License

MIT — see `LICENSE`.
