# Customizing knowledge-oss

The defaults are deliberately boring. Here is where each knob lives.

## Vault path

`rebuild_index.py` and `link_notes.py` operate on whatever directory you run
them from (or pass to `link_notes.py` as the first arg). `ingest_sources.py`
takes `--vault <path>` (default: cwd).

You can keep your vault anywhere on disk; clone this repo into that location
or copy the scripts in.

## Raw-source path

`ingest_sources.py --source-dir <path>` controls where it looks for raw
exports. Default: `~/raw-sources`. Inside it, the script expects:

```
<source-dir>/perplexity/         # Perplexity .md exports
<source-dir>/claude-sessions/    # Full Claude Code conversation logs
```

If you store sources elsewhere, pass `--source-dir` on every invocation, or
wrap the script in a shell alias.

## LLM provider / model

`link_notes.py` uses the Anthropic SDK and the model named at the top of the
file. To swap models, change that constant. To swap providers, replace the
`anthropic.Anthropic()` block in `llm_find_related()` with the provider of
your choice — keep the function signature and the JSON contract.

`ingest_sources.py` only calls the LLM when `--ai` is passed and the keyword
classifier returns `AMBIGUOUS`. Same swap rules apply.

`ANTHROPIC_API_KEY` is read from the environment.

## Prefix taxonomy

Note prefixes live in two places:

1. `rebuild_index.py` — the `MOC_SPECS` table at the top determines which
   prefixes get their own MOC and which get pulled into the glossary.
2. `README.md` — the human-facing prefix table.

To add a prefix `<thing>--`:
- decide whether it's glossary-eligible (concrete things with a TL;DR) or not
- add or extend the relevant `MOC_SPECS` entry
- add a row to the `README.md` prefix table
- run `python3 rebuild_index.py`

## Manifest format

Manifests live in `.manifests/` and are tab-separated:

- `perplexity.txt` — `<filename>\t<sha256>`
- `claude-sessions.txt` — `<filename>\t<sha256>\t<slug1>,<slug2>,...`
- `claude-sessions.ignore-patterns.txt` — substring patterns
  (case-insensitive, one per line, `#` comments). Sessions matching any
  pattern are auto-marked `IGNORED` on `claude-session list`.

## Memory layout

The seven memory files (`user.md`, `preferences.md`, `decisions.md`,
`people.md`, `current.md`, `future.md`, plus the `daily/` directory) are
referenced by name in `CLAUDE.md`. To add a new memory file, create it under
`memory/`, then add a bullet under the relevant section in `CLAUDE.md`.

## Daily-log format

`memory/daily/YYYY-MM-DD.md` files use H2 timestamps:

```markdown
## HH:MM — <headline>

<1-3 line body>
```

Newest at the bottom. The format is grep-friendly:
`grep "^## " memory/daily/2026-05-03.md` reads the day's headlines.

## Single-vault vs dual-vault

Single-vault is the default; dual-vault is a documented add-on
(`docs/dual-vault-pattern.md`). The scripts support both — `ingest_sources.py`
uses `--personal-vault` to switch modes; the rest are vault-agnostic.
