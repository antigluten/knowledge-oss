# Migrating an External Vault Into This Knowledge Base

Instructions for processing an existing flat markdown collection (another Obsidian
vault, a `~/notes/` directory, a Zettelkasten attempt, a folder of exported
journal entries) into `~/knowledge/` and `~/personal-knowledge/`.

This is a **bulk one-shot migration**, different from the routine ingestion flow
in the `ingest-to-vault` skill. The main differences:

- Volume: hundreds to thousands of files, not one at a time
- Quality: inconsistent — some notes are gold, most are noise
- Format: probably no frontmatter, no prefix scheme, raw titles
- Dedup: must reconcile against ~250 notes already in the target vaults
- Routing: split between technical and personal vaults during the same pass

## Target Audience for This Doc

A Claude Code session in this repo, or future-me, facing a folder of old markdown
that needs to enter the knowledge base without destroying it.

---

## Phase 0 — Inventory the source (always do this first)

Before touching anything, get honest numbers on what you're dealing with. Run in
the source directory:

```bash
export SRC=/path/to/old-vault     # adjust
cd "$SRC"

# How much are we talking about?
find . -name '*.md' -not -path '*/.*' | wc -l                 # total files
find . -name '*.md' -not -path '*/.*' -exec wc -l {} + | tail -1   # total lines
du -sh .                                                     # total size

# Distribution of file sizes (triage signal)
find . -name '*.md' -not -path '*/.*' -exec wc -c {} + \
  | awk '{print $1}' | sort -n | awk '
    NR==1{print "min:", $1}
    {a[NR]=$1}
    END{print "median:", a[int(NR/2)]; print "p90:", a[int(NR*0.9)]; print "max:", a[NR]}'

# Any frontmatter at all?
grep -l '^---$' **/*.md 2>/dev/null | wc -l

# Cyrillic content (routing signal)
grep -l '[А-Яа-я]' **/*.md 2>/dev/null | wc -l

# Obvious topic clusters by filename
ls *.md 2>/dev/null | sed 's/[-_].*//' | sort | uniq -c | sort -rn | head -20
```

Write the findings into `memory/daily/YYYY-MM-DD.md` so the decisions later have
context. Specifically capture:

- **Total file count + total size**
- **Median/p90 file size** — tells you whether most files are stubs (<1 KB) or
  substantive (>5 KB)
- **Frontmatter presence** — if zero have frontmatter, you'll be synthesizing it
  for every import
- **Language mix** — if any Cyrillic, tag `lang: ru` on those
- **Obvious clusters** — filename prefixes, dated journals, project folders

---

## Phase 1 — Strategy selection

Pick the strategy based on size:

### Small source (<100 files)

**Fully interactive via the `ingest-to-vault` skill, one by one.**

Just invoke the skill with each file. You'll read each one, decide classification,
write the clean note. Takes ~2 minutes per file. Fine for <100.

Skip the rest of this doc and use the skill directly.

### Medium source (100–500 files)

**Triage + batch ingest.** Proceed with Phase 2 onward.

### Large source (500+ files)

**Aggressive triage first** — assume 70–90% is noise, and build the pipeline to
cull it fast before you spend any effort on the remainder. Proceed with Phase 2,
but be extra ruthless with SKIP.

### Huge source (2000+ files)

**Consider: don't migrate everything.** At that volume, most notes are stale,
redundant, or low-value. Options:

1. **Time-windowed migration** — only import notes modified in the last N months
2. **Topic-windowed migration** — only import notes whose filenames/content match
   a priority topic list you care about right now
3. **Archive the whole source** as-is in `~/raw-sources/<source-name>/`
   and migrate on-demand when you actually need a specific old note

I would do (3) for anything 2000+. The vault is for active knowledge; dumping
2000 stale notes into it defeats the purpose.

---

## Phase 2 — Archive the source as immutable raw

Before any processing, copy the source into `~/raw-sources/`:

```bash
SOURCE_NAME=old-obsidian-vault   # pick a short, stable name
cp -R "$SRC" ~/raw-sources/"$SOURCE_NAME"
```

This is your immutable record. Even if migration goes sideways, the original is
safe. Never edit files in `~/raw-sources/` after this point.

Also: add a manifest entry in the dev vault. Create (or extend)
`~/knowledge/.manifests/<source-name>.txt` to track which files have
been processed. Same format as `claude-sessions.txt`:

```
filename<TAB>sha256<TAB>slug1,slug2,...
```

---

## Phase 3 — Triage pass (subagent, read-only)

Dispatch a read-only subagent to classify every source file into **SKIP / LIGHT
/ DEEP** and produce a ranked report. This is identical to the Claude-sessions
triage we do for session logs.

### Prompt template for the triage subagent

```
Read-only triage of files in ~/raw-sources/<SOURCE_NAME>/. Do NOT
modify any files or write to any vault.

Task: classify every .md file into SKIP/LIGHT/DEEP with a one-line reason and
estimated domain (technical / personal / both / unknown).

For each file, read only head -80 (or the whole file if <80 lines). Look for:
- Is there substantive reusable knowledge, or just fragments/thoughts?
- Single topic, multi-topic, or noise?
- Technical domain (iOS, Swift, systems, etc.) vs personal (health, travel, etc.)
- Language: en / ru / mixed
- Estimated note yield: 0 (SKIP), 1 (LIGHT), 2+ (DEEP)

Output a markdown report at /tmp/external-triage-<source-name>.md with:
- Summary counts per bucket
- DEEP list ranked by estimated value
- LIGHT list grouped by domain
- SKIP grouped by reason (stubs, duplicates of vault content, pure noise, stale
  drafts, TODO files, etc.)

Also check for obvious overlaps with the EXISTING vaults:
  ls ~/knowledge/ ~/personal-knowledge/
Note any source files whose topic is already covered in the target vaults —
flag those for merge-not-create.
```

The output report is your migration plan.

---

## Phase 4 — Bulk-mark the SKIPs

Before anything else, take all the SKIP files off the queue. Use the same
`bulk-mark` mechanism the claude-sessions flow uses. This will need a small
extension to `ingest_sources.py` — a generic `bulk-mark` subcommand that takes
a `--source <type>` parameter and a `--pattern` or `--file-list`.

If you don't want to extend the script, just write a one-off Python pass that
walks the SKIP list from the triage report and appends to the manifest with
empty slugs.

The point: make the source directory feel smaller immediately. Triaging 1000
files is daunting; triaging 150 remaining after SKIPs is manageable.

---

## Phase 5 — Pre-existing-notes check (DO NOT SKIP THIS)

**This is the step the dSYM-session ingest screwed up.** Learn from it.

Before writing any new notes, build a **topic map of the existing vaults** so
the migration subagents know what's already covered:

```bash
# Dump all existing titles + TL;DRs into one file
cd ~/knowledge
for f in concept--*.md arch-*--*.md dev-*--*.md bug-*--*.md tool--*.md synthesis--*.md; do
  [ -f "$f" ] || continue
  title=$(grep -m1 '^title:' "$f" | sed 's/^title: //')
  tldr=$(grep -m1 '^> \*\*TL;DR:\*\*' "$f" | sed 's/^> \*\*TL;DR:\*\* //')
  echo "$f | $title | $tldr"
done > /tmp/existing-tech-map.txt

cd ~/personal-knowledge
for f in concept--*.md; do
  [ -f "$f" ] || continue
  title=$(grep -m1 '^title:' "$f" | sed 's/^title: //')
  tldr=$(grep -m1 '^> \*\*TL;DR:\*\*' "$f" | sed 's/^> \*\*TL;DR:\*\* //')
  echo "$f | $title | $tldr"
done > /tmp/existing-personal-map.txt
```

These two files get passed to every migration subagent as context: "here is
what already exists, do not duplicate these, only extend or write net-new notes".

For topics that clearly overlap with existing notes, the subagent should either:

1. **Merge-extend** — add unique content from the source into the existing note,
   update `session_file:` to include a note about the merge, commit as an update
2. **Skip** — if the source doesn't add anything new, mark source as processed
   with the existing canonical's slug as provenance
3. **Different angle** — if the source genuinely covers a different angle, write
   a new note and cross-link via `related:`

Never silently duplicate.

---

## Phase 6 — Process LIGHT (batched, parallel)

LIGHT files each produce one note. These are safe to process in parallel.
Dispatch one subagent per batch of ~20–40 files:

- Each subagent reads its batch
- Checks against `/tmp/existing-*-map.txt` for duplicates
- Writes one clean note per source file (or skips if fully redundant)
- Marks each source file in the manifest with the produced slug
- Reports back with the list of notes written

Commit after each batch so if a subagent goes off the rails you can `git reset`
that batch cleanly.

## Phase 7 — Process DEEP (one at a time, interactive)

DEEP files each potentially produce 3–10 notes. These deserve human attention:

1. Read the source file yourself (or have Claude read and propose a breakdown)
2. Propose a list of notes: `slug — prefix — one-line TL;DR — target vault`
3. Get explicit approval on the breakdown
4. Dispatch a writer subagent with: the source file, the approved breakdown,
   and the `/tmp/existing-*-map.txt` files
5. Review the written notes before committing
6. Mark the source file in the manifest with all produced slugs

This is slow. For a medium source with 20 DEEP files, budget a few sessions.

---

## Phase 8 — Post-migration lint

After the migration is done:

1. Run the vault duplication audit (the same workflow used after the dSYM
   incident) to catch any overlaps the subagents introduced
2. Normalize `related:` frontmatter (script already exists — the loop from
   commit `cb94711`)
3. `python3 rebuild_index.py` in both vaults
4. Verify 0 broken links
5. Commit a lint pass entry in `log.md`
6. Update `memory/current.md` if the migration surfaced any durable life/project
   context changes
7. Append a summary entry in `memory/daily/YYYY-MM-DD.md`

---

## Anti-patterns — things that will burn you

- **Running the migration without Phase 5 (existing-notes check).** You will
  duplicate. Learned this the hard way with the dSYM session.
- **Trusting frontmatter heuristics for routing.** Many old notes have no
  frontmatter, and filename-based routing is unreliable. Read the content.
- **Skipping the raw-sources archive (Phase 2).** If you edit source files in
  place, you lose the ability to re-run the migration cleanly.
- **Committing hundreds of notes in one commit.** Commit per batch, ideally
  per topic cluster. Easier to review, easier to revert, easier to attribute.
- **Rewriting content you don't understand.** If a note is in a domain you're
  not fluent in (e.g. Chinese medicinal herbs, obscure game lore), don't try
  to rewrite it. Either preserve it verbatim with a note explaining the
  limitation, or skip it.
- **Bulk-importing journal entries verbatim.** Daily journal dumps almost never
  belong in the knowledge vault as-is. If you have 600 journal entries, synthesize
  them into thematic notes instead: "patterns in my 2024 mental state" rather than
  600 dated stubs.
- **Ignoring Cyrillic content.** The ingest pipeline supports `lang: ru` — use
  it. Don't translate unnecessarily.

---

## Rough effort estimate

| Source size | Triage | Bulk-SKIP | LIGHT batch | DEEP batch | Lint | Total |
|---|---|---|---|---|---|---|
| 100 files | 15 min | 5 min | 1–2 sessions | 0–1 session | 15 min | 1 day |
| 500 files | 30 min | 10 min | 3–5 sessions | 2–3 sessions | 30 min | 1 week |
| 2000 files | 1 hour | 20 min | 10+ sessions | 5+ sessions | 1 hour | several weeks OR don't migrate everything |

Most of the time is the DEEP phase. That's the phase you can't parallelize.

---

## One-off tools you might want to build

If migration becomes recurring rather than one-off, consider building:

1. **`ingest_sources.py external <source-name>`** — generic external-vault ingest
   subcommand that takes a raw-sources subdirectory, reads from a triage report,
   and dispatches workers
2. **`--existing-map`** flag on the skill that loads `/tmp/existing-*-map.txt`
   automatically
3. **`duplication-audit.py`** — the vault audit from the dSYM incident, scripted
   so it runs on every commit or weekly
4. **Mirror into `memory/daily/`** — auto-log migration progress into the daily
   file so you can see burn-down over time

Defer all of these until you've migrated at least one external vault manually.
Don't optimize a workflow you haven't run yet.

---

## Pre-commit checklist

Before committing each batch during migration:

- [ ] Existing-notes map checked for overlap
- [ ] No duplicate slugs created
- [ ] Source files marked in the manifest with produced slugs
- [ ] `rebuild_index.py` run, 0 broken links
- [ ] `log.md` entry appended
- [ ] Today's `memory/daily/*.md` has a progress entry
- [ ] Personal-context notes routed to personal vault (not tech)
- [ ] Commit message mentions source name and batch scope
