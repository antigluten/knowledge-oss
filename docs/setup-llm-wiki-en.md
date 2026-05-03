# Set Up Your Own LLM Wiki

A shareable recipe for building a persistent, LLM-curated knowledge vault — the kind of setup that turns every Claude/Cursor/opencode session into a stream of atomic notes you can grep, link, and re-enter months later.

## What this is

A flat directory of markdown notes with filename prefixes, YAML frontmatter, Obsidian-style `[[wikilinks]]`, and a small Python script that regenerates indexes on demand. The LLM reads it at session start (via `CLAUDE.md` instructions), so it can cite your prior work instead of re-deriving everything from scratch.

## Lineage

This recipe is a concrete implementation of the pattern Andrej Karpathy describes in [*The agent-maintained LLM wiki*](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). He names the core architecture — three layers (**raw sources → agent-owned wiki → schema document**), the ingest/query/lint workflow, `index.md` + `log.md` with the `## [YYYY-MM-DD] event | title` prefix pattern, and the philosophy that *"the LLM handles the bookkeeping; the human curates sources, asks good questions, and thinks about what it all means."* If you haven't read the gist, read it first — it's short and explains the *why* better than this file does.

This guide fills in the opinionated specifics that Karpathy intentionally leaves open:

- A fleshed-out filename-prefix scheme (`concept--`, `arch-decision--`, `bug-pattern--`, …) that maps cleanly to the ingest workflow.
- An auto-generated `glossary.md` alongside the index, sourced from each note's `> **TL;DR:**` line.
- A static-vs-live split of the memory layer (`user.md` / `preferences.md` vs. `current.md` / `future.md` / `daily/`) giving the LLM both identity context and session-specific state.
- A drop-in `CLAUDE.md` and working `rebuild_index.py` so you can bootstrap in 15 minutes without writing anything yourself.

## Why you want it

- **Chat history decays.** Closed tabs are gone. Atomic notes survive.
- **grep is your RAG.** 300 atomic notes are navigable with `ls prefix--*` + `grep` — no vector DB required.
- **LLMs are great at summarizing.** Let Claude pull the durable insight out of a 2-hour debug session into one reusable note.
- **Forkable + private.** It's a git repo of plain text. No server, no SaaS, no vendor lock-in.

## Architecture at a glance

```
~/my-knowledge/
├── CLAUDE.md                    ← instructions Claude reads at session start
├── README.md                    ← optional human-facing entry point
├── log.md                       ← append-only chronological timeline
├── memory/                      ← who you are, what you're working on
│   ├── user.md                  ←   static identity
│   ├── preferences.md           ←   how you like to work
│   ├── decisions.md             ←   architectural decisions across projects
│   ├── people.md                ←   who's who
│   ├── current.md               ←   live project/priority snapshot
│   ├── future.md                ←   upcoming plans + ideas
│   └── daily/
│       └── YYYY-MM-DD.md        ←   daily working log
├── moc--master-index.md         ← top-level catalog (auto-generated)
├── moc--*.md                    ← per-domain tables of contents (auto-generated)
├── glossary.md                  ← A–Z term index (auto-generated)
├── concept--*.md                ← atomic knowledge notes
├── arch-decision--*.md          ← ADRs
├── arch-pattern--*.md
├── arch-system--*.md
├── bug-issue--*.md              ← specific bugs + fixes
├── bug-pattern--*.md            ← recurring failure modes
├── dev-snippet--*.md            ← code snippets
├── dev-workflow--*.md           ← workflows / procedures
├── dev-config--*.md             ← configuration notes
├── tool--*.md                   ← tool documentation
├── synthesis--*.md              ← cross-note analyses / filed query answers
└── rebuild_index.py             ← regenerates MOCs + glossary
```

**Everything is flat.** No folders for categories — filename prefix does the grouping. Why: `ls concept--ios*` works anywhere; moving a note across "categories" is a rename, not a directory shuffle; Obsidian's graph view shows the whole vault in one mesh.

## The note template

Every content note follows this shape:

```markdown
---
title: Human Readable Title
tags: [domain, type, maturity]
lang: en
created: 2026-04-18
source: claude-session
session_file: original-export-filename.md
related: []
---

# Human Readable Title

> **TL;DR:** One sentence summary — this is what lands in the glossary.

## Detail

Prose, code blocks, whatever the topic needs.
```

**Rules:**
- `title:` is what humans read. Quote it with `"..."` if it contains `:` or other YAML specials.
- `tags:` — one domain (ios, swift, backend, lifestyle, etc.), one type (concept, pattern, decision, …), one maturity (`draft` or `mature`).
- `lang:` — `en` or `ru`. Detect from body.
- `source:` — where the note came from (`claude-session`, `perplexity`, `manual`, …).
- `related:` — list of note stems you think are adjacent. The LLM can be asked to fill this during ingest.
- The `> **TL;DR:**` line is **load-bearing** — it feeds the auto-generated glossary.

## Filename prefixes

| Prefix | Use for |
|---|---|
| `concept--` | atomic definitions of terms/ideas |
| `arch-decision--` | ADR-style decisions with rationale |
| `arch-pattern--` | reusable architectural patterns |
| `arch-system--` | system-level overviews |
| `bug-issue--` | one specific bug + its fix |
| `bug-pattern--` | recurring failure modes |
| `dev-snippet--` | code snippets |
| `dev-workflow--` | procedures / workflows |
| `dev-config--` | configuration files / settings |
| `tool--` | tool documentation |
| `synthesis--` | cross-note analyses, filed query answers |

Slug format: `prefix--slugified-title.md` — lowercase, hyphenated, max ~6 words.

## Memory files

Split memory into **static** (changes rarely) and **live** (changes per session).

**Static** (create once, edit as things change):
- `memory/user.md` — who you are, your role, your expertise.
- `memory/preferences.md` — coding style, response style, things you've told the LLM to stop doing.
- `memory/decisions.md` — architectural decisions you've committed to across projects.
- `memory/people.md` — collaborators, teams, recurring names.

**Live** (update every session):
- `memory/current.md` — active projects, priorities, blockers. A snapshot of "right now."
- `memory/future.md` — planned events, upcoming work, ideas to explore.
- `memory/daily/YYYY-MM-DD.md` — append-only log for the day: `## HH:MM — <headline>` sections.

The LLM reads all of these at session start (instructed by `CLAUDE.md`). When the session ends, it updates `current.md` / `future.md` if anything shifted, and appends to the daily log.

## log.md — vault timeline

A single append-only file at the root recording meaningful vault operations. One entry per ingest, synthesis, or cleanup pass:

```markdown
## [2026-04-18] ingest | 38 Claude sessions → 28 new notes

Brief context (1–3 lines).
```

Events: `ingest`, `synthesis`, `query` (only when the answer was itself filed), `lint`, `meta`. Skip trivial chats.

Grep-friendly: `grep "^## \[" log.md | tail -20`.

## Bootstrap

```bash
mkdir -p ~/my-knowledge/memory/daily ~/my-knowledge/.manifests
cd ~/my-knowledge
git init
```

Create `CLAUDE.md` (copy-paste the starter below), create `rebuild_index.py` (copy-paste below), write your first note by hand, run `python3 rebuild_index.py`, commit.

### Starter `CLAUDE.md`

```markdown
# Claude Code Instructions — Knowledge Vault

## Memory: Read at Session Start

At the start of every session in this directory, silently read:

**Static** (identity + preferences — rarely change):
- `memory/user.md`
- `memory/preferences.md`
- `memory/decisions.md`
- `memory/people.md`

**Live** (change often — always read these):
- `memory/current.md`
- `memory/future.md`
- The most recent file in `memory/daily/` (previous day or two)

Also skim the tail of `log.md`:

    grep "^## \[" log.md | tail -20
    ls -t memory/daily/ | head -3

## Log.md — Append-Only Timeline

Append one entry per ingest, synthesis, or cleanup pass:

    ## [YYYY-MM-DD] <event> | <title>

    <1–3 line context>

Events: `ingest`, `synthesis`, `query`, `lint`, `meta`. Skip trivial chats.

## Memory Updates

**During the session — append to the daily log:**

Every meaningful decision or context shift gets an entry in `memory/daily/YYYY-MM-DD.md`:

    ## HH:MM — <headline>

    <1–3 line body>

Append in chronological order, newest at the bottom.

**At session end:**
- Update `memory/current.md` if projects/priorities/blockers shifted.
- Update `memory/future.md` if new events/plans/ideas surfaced.
- Update static memory only for durable new facts (new tool, new preference, new decision).

## Note Conventions

- Flat vault — all notes in root. Filename prefix is the category.
- Frontmatter: `title`, `tags`, `lang`, `created`, `source`, `related`.
- Every note starts with `# Title` then `> **TL;DR:** <one sentence>`.
- Wikilinks: `[[stem]]` — no `.md` extension.
- Prefixes: `concept--`, `arch-decision--`, `arch-pattern--`, `arch-system--`, `bug-issue--`, `bug-pattern--`, `dev-snippet--`, `dev-workflow--`, `dev-config--`, `tool--`, `synthesis--`.

## Key Scripts

- `python3 rebuild_index.py` — regenerates all MOC files + `glossary.md`. Run after every note add / rename / title edit.

## Filing Chat Query Results

When a conversation produces a substantive synthesized answer (comparison, analysis, cross-note connection), offer to file it as `synthesis--<slug>.md`. Add a `log.md` entry.
```

### Starter `rebuild_index.py`

Drop-in, zero external deps, ~150 lines. Regenerates all MOCs, a master index, and a glossary, and reports broken wikilinks.

```python
#!/usr/bin/env python3
"""Rebuild MOC files, master index, and glossary from existing vault notes."""

import re
from pathlib import Path
from collections import defaultdict
from datetime import date as dt

VAULT = Path(__file__).parent

FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---', re.DOTALL)
TLDR_RE = re.compile(r'>\s*\*\*TL;DR:\*\*\s*(.+)')
WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')
FENCED_CODE_RE = re.compile(r'```.*?```', re.DOTALL)
INLINE_CODE_RE = re.compile(r'`[^`\n]+`')
LEADING_ARTICLE_RE = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)


def parse_frontmatter(content):
    m = FRONTMATTER_RE.match(content)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            result[key.strip()] = val
    return result


def scan_notes(vault):
    notes = []
    for path in sorted(vault.glob("*.md")):
        stem = path.stem
        if stem.startswith(("_template", "moc--")) or stem in ("log", "CLAUDE", "README", "glossary"):
            continue
        content = path.read_text()
        fm = parse_frontmatter(content)
        tldr_m = TLDR_RE.search(content)
        notes.append({
            "path": path, "stem": stem,
            "title": fm.get("title", stem),
            "tldr": tldr_m.group(1).strip() if tldr_m else "",
            "content": content,
        })
    return notes


def strip_code(content):
    return INLINE_CODE_RE.sub('', FENCED_CODE_RE.sub('', content))


def _link_target(link):
    return link.split("|", 1)[0].split("#", 1)[0].strip()


def count_wikilinks(notes):
    counts = defaultdict(int)
    for n in notes:
        for link in WIKILINK_RE.findall(strip_code(n["content"])):
            counts[_link_target(link)] += 1
    return counts


def find_broken(notes, vault):
    stems = {n["stem"] for n in notes}
    broken = []
    for n in notes:
        for link in WIKILINK_RE.findall(strip_code(n["content"])):
            target = _link_target(link)
            if target not in stems and not (vault / f"{target}.md").exists():
                broken.append(f"{n['stem']}: [[{link}]]")
    return broken


def _note_line(n):
    return f"- [[{n['stem']}]] — {n['tldr'] or n['title']}"


def build_moc(title, prefixes, notes):
    matching = [n for n in notes if any(n["stem"].startswith(p) for p in prefixes)]
    lines = ["---", f"title: {title}", "tags: [moc, index]", "---", "", f"# {title}", ""]
    lines += [_note_line(n) for n in matching] if matching else ["_No notes yet._"]
    return "\n".join(lines) + "\n"


MOC_SPECS = [
    ("moc--architecture.md", "Architecture", ["arch-decision--", "arch-pattern--", "arch-system--"]),
    ("moc--development.md",  "Development",  ["dev-snippet--", "dev-workflow--", "dev-config--"]),
    ("moc--debugging.md",    "Debugging",    ["bug-issue--", "bug-pattern--"]),
    ("moc--tools.md",        "Tools",        ["tool--"]),
    ("moc--concepts.md",     "Concepts",     ["concept--"]),
    ("moc--synthesis.md",    "Synthesis",    ["synthesis--"]),
]

GLOSSARY_PREFIXES = ("concept--", "arch-pattern--", "arch-system--",
                     "arch-decision--", "bug-pattern--", "tool--")


def _gkey(title):
    return LEADING_ARTICLE_RE.sub("", title).lower()


def _gletter(title):
    k = _gkey(title)
    if not k:
        return "#"
    c = k[0].upper()
    return c if c.isalpha() else "0-9"


def build_glossary(notes):
    entries = sorted(
        (n for n in notes if any(n["stem"].startswith(p) for p in GLOSSARY_PREFIXES)),
        key=lambda n: _gkey(n["title"]),
    )
    lines = ["---", "title: Glossary", "tags: [moc, index, glossary]", "---", "",
             "# Glossary", "",
             "> A–Z term index. Auto-generated by `rebuild_index.py` — do not edit.", ""]
    buckets = defaultdict(list)
    for n in entries:
        buckets[_gletter(n["title"])].append(n)
    for letter in sorted(buckets, key=lambda x: (0, "") if x == "0-9" else (1, x)):
        lines += [f"## {letter}", ""]
        for n in buckets[letter]:
            defn = n["tldr"] or "_No TL;DR yet._"
            lines += [f"**{n['title']}** — {defn} See [[{n['stem']}]].", ""]
    lines += ["---", "", f"_Total terms: {len(entries)}_", ""]
    return "\n".join(lines) + "\n"


def build_master(notes, link_counts):
    top = sorted(link_counts.items(), key=lambda x: -x[1])[:10]
    lines = ["---", "title: Master Index", "tags: [moc, index]", "---", "",
             "# Master Index", "", "## By Domain", "",
             "- [[moc--architecture]]", "- [[moc--development]]", "- [[moc--debugging]]",
             "- [[moc--tools]]", "- [[moc--concepts]]", "- [[moc--synthesis]]",
             "- [[glossary]]", "", "## Top Linked Concepts", ""]
    lines += [f"- [[{s}]] ({c} ref{'s' if c != 1 else ''})" for s, c in top] or ["_No links yet._"]
    lines += ["", f"_Total notes: {len(notes)}_", ""]
    return "\n".join(lines) + "\n"


def main():
    notes = scan_notes(VAULT)
    link_counts = count_wikilinks(notes)
    broken = find_broken(notes, VAULT)

    for filename, title, prefixes in MOC_SPECS:
        (VAULT / filename).write_text(build_moc(title, prefixes, notes))
    (VAULT / "moc--master-index.md").write_text(build_master(notes, link_counts))
    (VAULT / "glossary.md").write_text(build_glossary(notes))

    print(f"\n=== rebuild_index summary ({dt.today().isoformat()}) ===")
    print(f"Notes:          {len(notes)}")
    print(f"MOC files:      {len(MOC_SPECS) + 1}")
    print(f"Glossary terms: {sum(1 for n in notes if any(n['stem'].startswith(p) for p in GLOSSARY_PREFIXES))}")
    print(f"Broken links:   {len(broken)}")
    for b in broken:
        print(f"  WARNING: {b}")
    print()


if __name__ == "__main__":
    main()
```

## Have Claude bootstrap this for you

Don't want to copy-paste the scripts yourself? In a fresh Claude Code / Cursor / opencode session, `cd` into an empty directory and paste this prompt along with this whole document:

> Read the attached setup guide end-to-end. Then create a fresh LLM wiki at `./` following it exactly:
>
> 1. Create the directory tree (`memory/daily/`, `.manifests/`).
> 2. Write `CLAUDE.md` copying the "Starter `CLAUDE.md`" block verbatim.
> 3. Write `rebuild_index.py` copying the "Starter `rebuild_index.py`" block verbatim.
> 4. Create empty stubs for each memory file: `memory/user.md`, `memory/preferences.md`, `memory/decisions.md`, `memory/people.md`, `memory/current.md`, `memory/future.md`, `memory/daily/<today>.md`. Each should have a one-line H1 matching the filename.
> 5. Create `log.md` with a title header and one `## [<today>] meta | vault bootstrapped` entry.
> 6. `git init` and make the initial commit.
> 7. Run `python3 rebuild_index.py` once to generate the initial MOCs and glossary.
> 8. Then interactively ask me to fill in `memory/user.md` (who I am, role, expertise) and `memory/preferences.md` (how I want you to work). Those are the only two I have to write myself.

This document contains every artifact Claude needs to do that without follow-up questions.

## Daily workflow

### In a normal chat session

Claude reads `memory/` + `log.md` at session start (because `CLAUDE.md` tells it to). It now has context on who you are and what you're working on. As the session produces decisions or context shifts, it appends to `memory/daily/YYYY-MM-DD.md`.

### When a session produces durable knowledge

Turn it into a note. Ask Claude something like:

> "File this as a concept note in the vault — `concept--<slug>.md`. Include TL;DR, frontmatter, and a wikilink to `[[related-note]]` if relevant. Append a log entry."

It writes the note; you review; run `python3 rebuild_index.py`; commit.

### When you run out of context mid-topic

Ask Claude to synthesize. When the answer is substantive (comparison, cross-note connection, decision memo), file it as `synthesis--<slug>.md`. Same ingest flow.

### Periodically

Run a **lint pass** — ask Claude to audit the vault for orphans (zero inbound wikilinks), stale drafts (`draft` tag, old, ≥3 inbound links), contradictions, missing concept pages, broken links. Fix or ignore per your taste.

## Ingesting external content

Useful for Perplexity exports, ChatGPT shared chats, research articles, old notes in other formats.

Simple version: drop the raw file somewhere (e.g. `~/raw-sources/perplexity/foo.md`), ask Claude to read it, extract the note-worthy bits, and write one or more vault notes. Use the template. Add `source: perplexity` in frontmatter with `session_file:` pointing at the original filename — preserves provenance.

Advanced version (optional): track ingested files with SHA-256 hashes in a `.manifests/` directory so re-runs skip unchanged files and flag edited ones. Wrap in a shell script or Python CLI.

## Optional extras

### Semantic cross-linker

A short Python script that hits the Anthropic API, gives it batches of your notes, and asks "which notes are adjacent to which?" then fills in `related:` frontmatter. Needs `ANTHROPIC_API_KEY`. Run it after big ingests, not every time — it costs money.

### Ingest skill

If you use Claude Code: wrap the ingest workflow in a `~/.claude/skills/ingest-to-vault/SKILL.md` so `/ingest-to-vault` becomes a one-command pipeline. Saves typing the same instructions every time.

### Graph view

Install Obsidian and open the vault. Wikilinks turn into a visual graph. Useful for spotting hub notes and isolated clusters.

### Two vaults

One technical, one personal. Same shape, different directory. Personal stays out of any work / GitHub context. A rule in `CLAUDE.md` routes personal context (health, travel, relationships) to the personal vault's daily log even if it surfaces in a technical session.

## Tips and gotchas

- **Keep notes atomic.** One note = one idea. A note that's 3 pages long is 4 notes that need splitting.
- **Descriptive titles.** The title ends up in the glossary and the master index. "iOS bug" is useless; "UIViewController deinit race with CADisplayLink" is useful.
- **TL;DR is mandatory.** Without it, the glossary entry is blank. One sentence, actionable.
- **Don't over-categorize.** Four or five prefixes cover 90% of cases. Resist the urge to invent `concept-advanced--` or `arch-pattern-experimental--`.
- **Commit often.** The vault is a git repo — commits are free backups and make the timeline searchable.
- **The vault is for you first.** Don't write notes imagining a public audience; you'll stall. Private-by-default, share when useful.
- **Obsidian is optional.** The vault is plain markdown. Obsidian just adds graph view + backlinks UI. VS Code + grep works fine.

## When this starts to pay off

Around note #50–100 it clicks. The LLM starts citing your own prior work back to you. You realize you already solved this problem six months ago. The cost of maintenance drops below the cost of re-deriving.

Before note #50 it feels like overhead. Push through.

## Reference layout

A working vault following this layout sits at `~/knowledge` — flat markdown, frontmatter-driven, MOC + glossary regenerated on demand. Structure is exactly what's described above. The scripts in this repo are ready to crib verbatim.
