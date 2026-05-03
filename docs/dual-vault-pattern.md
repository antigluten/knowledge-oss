# Dual-vault pattern (optional)

The default `knowledge-oss` setup is single-vault: everything goes in one place.
This works fine until your context starts mixing — say, work code one minute,
travel logistics the next. At that point, splitting into two vaults keeps each
context clean.

## When to adopt

- You start noticing personal items leaking into work-facing logs (or vice versa).
- You want to share one vault publicly (e.g. a tech-only digital garden) but keep
  the other private.
- A single Claude session wants to commit to two different topics and the daily
  log feels schizophrenic.

## Two vaults, one pattern

```
~/knowledge/             # technical / work / project context
~/personal-knowledge/    # health, travel, finance, relationships, etc.
```

Each is its own git repo, each has the same flat layout (scripts, `memory/`,
`.manifests/`, `log.md`). The scripts ship with `--vault` and `--personal-vault`
flags so you can ingest into both from one CLI invocation:

```bash
python3 ingest_sources.py \
  --vault ~/knowledge \
  --personal-vault ~/personal-knowledge \
  --source-dir ~/raw-sources \
  perplexity
```

The keyword classifier in `ingest_sources.py` decides per-source whether each
note goes to the technical or personal vault.

## Cross-vault routing in `CLAUDE.md`

Add this section to **both** vaults' `CLAUDE.md` (with the paths flipped in the
personal one):

```markdown
## Cross-Vault Routing Rule

This vault's daily log is for **technical / work / project** context only.

If personal context surfaces in a session here (health, relationships, travel,
finance, life decisions) — route it to the personal vault instead:

1. Append the full entry to `~/personal-knowledge/memory/daily/YYYY-MM-DD.md`
   (create if missing).
2. In this vault's daily log, leave only a pointer line:
   `## HH:MM — personal context → ~/personal-knowledge/memory/daily/YYYY-MM-DD.md`
3. Do not duplicate the content between the two logs.

Symmetrically, if tech context surfaces during a session started in the personal
vault, route it to this vault's daily log.
```

## Authorship-marker pipeline (optional add-on to dual-vault)

When Claude *generates* a note for the personal vault from raw research (rather
than the user authoring it), mark its provenance so future sessions can
distinguish user-written notes from agent-written ones.

Convention:

- Manually-authored notes use a `## From the user` header for the user's prose
  and an optional `## Added by Claude (YYYY-MM-DD)` header for the assistant's
  copy-edits.
- Fully agent-authored notes carry `authored_by: claude` in frontmatter and
  open with an Obsidian `[!claude]` callout naming the source and date.

`ingest_sources.py` already emits the callout when ingesting into a personal
vault. The marker keeps your "I wrote this" notes legible from your "Claude
summarized this for me" notes.
