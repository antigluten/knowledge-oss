#!/usr/bin/env python3
"""Unified ingest for raw sources into the knowledge vault.

Raw sources live under <source-dir>/<type>/ (default ~/raw-sources/<type>/) and
manifests live in <vault>/.manifests/<type>.txt so they're git-tracked.

Single-vault mode (default): pass --vault <path>. Everything routes there.
Dual-vault mode (optional): also pass --personal-vault <path> to route
classified-as-PERSONAL notes there instead.

Subcommands:
    perplexity                  Batch-ingest new/changed Perplexity exports.
    perplexity --ai             Use Claude API for ambiguous classification.
    perplexity --force F        Re-process specific Perplexity files.
    claude-session list         List raw Claude session files not yet processed.
    claude-session mark F [--slugs slug1,slug2]
                                Mark a Claude session as processed (record
                                which note slugs it produced).

Manifest format (tab-separated):
    perplexity.txt        filename\\thash
    claude-sessions.txt   filename\\thash\\tslug1,slug2,...
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path
from datetime import date

# Defaults — overridable via CLI flags --vault, --personal-vault, --source-dir.
# We resolve concrete paths inside main() / _cmd_* once flags are parsed.
DEFAULT_VAULT = Path.cwd()
DEFAULT_RAW_ROOT = Path.home() / "raw-sources"


def _vault_paths(vault: Path) -> dict:
    """Return derived paths under a given vault root."""
    manifests = vault / ".manifests"
    return {
        "vault": vault,
        "manifests": manifests,
        "perplexity_manifest": manifests / "perplexity.txt",
        "claude_manifest": manifests / "claude-sessions.txt",
        "claude_ignore_patterns": manifests / "claude-sessions.ignore-patterns.txt",
        "processed_index": vault / ".processed_notes.txt",
    }


def _source_paths(source_dir: Path) -> dict:
    """Return derived paths under a given raw-source root."""
    return {
        "perplexity_dir": source_dir / "perplexity",
        "claude_sessions_dir": source_dir / "claude-sessions",
    }

# Authorship markers for fully-Claude-authored personal-vault notes.
# Spec: docs/superpowers/specs/2026-05-02-personal-vault-note-pipeline-design.md
AUTHORED_BY_CLAUDE_FRONTMATTER = "authored_by: claude"
CLAUDE_CALLOUT_TEMPLATE = "> [!claude] Authored by Claude — ingested from {source}, {date}."

TECHNICAL_KEYWORDS: set[str] = {
    # English
    "swift", "python", "javascript", "typescript", "rust", "go", "sql", "api",
    "database", "kubernetes", "docker", "compiler", "algorithm", "architecture",
    "backend", "frontend", "server", "xcode", "swiftui", "git", "debug",
    "function", "class", "struct", "protocol", "async", "thread", "memory",
    "framework", "library", "deploy", "networking", "http", "json", "rest",
    # Russian
    "программирование", "разработка", "код", "функция", "класс",
    "база данных", "сервер", "алгоритм", "архитектура", "компилятор",
    "библиотека", "фреймворк", "приложение", "отладка", "деплой",
}

PERSONAL_KEYWORDS: set[str] = {
    # English
    "health", "fitness", "workout", "nutrition", "recipe", "food",
    "travel", "climbing", "sport", "finance", "budget", "sleep",
    "book", "movie", "music", "hobby", "shopping", "family",
    "relationship", "meditation", "wellness", "diet", "exercise",
    "investment", "savings", "hiking", "yoga", "mental",
    "visa", "nomad", "residency", "tax", "running", "marathon",
    # Russian
    "здоровье", "питание", "тренировка", "путешествие", "рецепт",
    "еда", "скалолазание", "спорт", "финансы", "бюджет", "сон",
    "книга", "фильм", "музыка", "хобби", "семья", "отношения",
    "медитация", "диета", "упражнение", "инвестиции", "походы",
    "виза", "кочевник", "внж", "налог", "пробежка", "марафон",
    "резидент", "нерезидент", "одевать",
}


def keyword_classify(title: str, content: str) -> str:
    """Return 'TECHNICAL', 'PERSONAL', or 'AMBIGUOUS' based on keyword scoring."""
    text = (title + " " + content[:500]).lower()
    tech_score = sum(1 for kw in TECHNICAL_KEYWORDS if kw in text)
    personal_score = sum(1 for kw in PERSONAL_KEYWORDS if kw in text)
    if tech_score > personal_score:
        return "TECHNICAL"
    if personal_score > tech_score:
        return "PERSONAL"
    return "AMBIGUOUS"


def file_hash(path: Path) -> str:
    """Return SHA-256 hex digest of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_processed(manifest: Path) -> dict[str, str]:
    """Return dict of {filename: hash} from manifest. Supports old format (no hash)."""
    if not manifest.exists():
        return {}
    result = {}
    for line in manifest.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        if "\t" in line:
            name, h = line.split("\t", 1)
            result[name] = h
        else:
            result[line] = ""
    return result


def get_existing_notes(index_path: Path) -> set[str]:
    """Return set of note slugs already in vaults (from .processed_notes.txt)."""
    if not index_path.exists():
        return set()
    return {
        line.strip()
        for line in index_path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def mark_note_indexed(index_path: Path, note_slug: str) -> None:
    """Append a note slug to the processed notes index."""
    with index_path.open("a") as f:
        f.write(note_slug + "\n")


def mark_processed(manifest: Path, filename: str, content_hash: str = "") -> None:
    """Append filename and hash to manifest file."""
    with manifest.open("a") as f:
        f.write(f"{filename}\t{content_hash}\n")


def extract_title(content: str, filename: str) -> str:
    """Extract title from first # heading, or derive from filename."""
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    stem = Path(filename).stem
    return stem.replace("-", " ").replace("_", " ").title()


def slugify(title: str) -> str:
    """Convert title to lowercase-hyphenated slug, max 6 words."""
    cleaned = re.sub(r'[^\w\s]', '', title.lower())
    words = cleaned.split()
    return "-".join(words[:6])


def detect_lang(content: str) -> str:
    """Return 'ru' if content contains Cyrillic characters, else 'en'."""
    if re.search(r'[а-яёА-ЯЁ]', content):
        return "ru"
    return "en"


def _anthropic_client():
    """Lazy-load Anthropic client. Raises ImportError if anthropic not installed."""
    try:
        import anthropic
        return anthropic.Anthropic()
    except ImportError:
        raise ImportError("Install anthropic SDK: pip install anthropic")


def llm_classify(title: str, content: str) -> str:
    """Use Claude API to classify ambiguous content. Returns 'TECHNICAL' or 'PERSONAL'."""
    client = _anthropic_client()
    prompt = (
        "Classify this note as TECHNICAL or PERSONAL. "
        "The content may be in English or Russian.\n"
        "TECHNICAL = programming, software, systems, engineering, computer science.\n"
        "PERSONAL = health, lifestyle, travel, relationships, finance, hobbies.\n\n"
        f"Title: {title}\n"
        f"Content preview: {content[:300]}\n\n"
        "Reply with exactly one word: TECHNICAL or PERSONAL"
    )
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    block = message.content[0]
    text = getattr(block, "text", "")
    result = text.strip().upper()
    return result if result in ("TECHNICAL", "PERSONAL") else "PERSONAL"


def classify(title: str, content: str, use_ai: bool = False) -> str:
    """Keyword classifier with optional LLM fallback for AMBIGUOUS.

    Without --ai, AMBIGUOUS defaults to TECHNICAL (safer — easier to move later).
    """
    result = keyword_classify(title, content)
    if result == "AMBIGUOUS":
        if use_ai:
            result = llm_classify(title, content)
        else:
            print(f"    AMBIGUOUS (defaulting to TECHNICAL): {title[:60]}")
            result = "TECHNICAL"
    return result


def build_note(
    title: str,
    content: str,
    filename: str,
    classification: str,
) -> tuple[str, str]:
    """Build note content and filename. Returns (note_content, note_filename).

    Personal-vault notes get an `authored_by: claude` frontmatter field and a
    `> [!claude] ...` callout block right after the TL;DR. Technical notes are
    unchanged. Currently used only on the Perplexity ingest path; the source
    string is hardcoded to "perplexity" in both the frontmatter and the
    callout. Spec: docs/superpowers/specs/2026-05-02-personal-vault-note-pipeline-design.md
    """
    today = date.today().isoformat()
    lang = detect_lang(title + " " + content)
    slug = slugify(title)
    note_filename = f"concept--{slug}.md"
    domain = "backend" if classification == "TECHNICAL" else "lifestyle"

    # Each piece carries its own trailing whitespace so it renders as nothing
    # for TECHNICAL or as a complete inserted block for PERSONAL.
    is_personal = classification == "PERSONAL"
    authored_by_line = f"{AUTHORED_BY_CLAUDE_FRONTMATTER}\n" if is_personal else ""
    callout_block = (
        f"{CLAUDE_CALLOUT_TEMPLATE.format(source='perplexity', date=today)}\n\n"
        if is_personal
        else ""
    )

    note_content = (
        f"---\n"
        f"title: {title}\n"
        f"tags: [{domain}, concept, draft]\n"
        f"lang: {lang}\n"
        f"created: {today}\n"
        f"source: perplexity\n"
        f"{authored_by_line}"
        f"session_file: {filename}\n"
        f"related: []\n"
        f"---\n"
        f"\n"
        f"# {title}\n"
        f"\n"
        f"> **TL;DR:** Extracted from Perplexity research on {title}.\n"
        f"\n"
        f"{callout_block}"
        f"## Detail\n"
        f"{content.strip()}\n"
    )
    return note_content, note_filename


def ingest_file(
    export_path: Path,
    vault: Path,
    personal_vault: Path | None,
    manifest: Path,
    processed_index: Path,
    existing_notes: set[str] | None = None,
    use_ai: bool = False,
    force: bool = False,
) -> str | None:
    """Process one export file. Writes note to correct vault. Returns classification or None if skipped.

    If `personal_vault is None`, single-vault mode: everything routes to `vault`
    regardless of classification.
    """
    content = export_path.read_text(encoding="utf-8")
    content_hash = file_hash(export_path)
    title = extract_title(content, export_path.name)
    classification = classify(title, content, use_ai=use_ai)

    # Routing: only divert to personal_vault if it's configured AND content is PERSONAL.
    if personal_vault is not None and classification == "PERSONAL":
        target = personal_vault
    else:
        target = vault
    target.mkdir(parents=True, exist_ok=True)

    note_content, note_filename = build_note(title, content, export_path.name, classification)
    note_slug = Path(note_filename).stem

    # Skip if note already exists in either vault (unless forced)
    if not force:
        if existing_notes and note_slug in existing_notes:
            mark_processed(manifest, export_path.name, content_hash)
            return None
        if (vault / note_filename).exists() or (
            personal_vault is not None and (personal_vault / note_filename).exists()
        ):
            mark_processed(manifest, export_path.name, content_hash)
            return None

    (target / note_filename).write_text(note_content, encoding="utf-8")
    mark_processed(manifest, export_path.name, content_hash)
    mark_note_indexed(processed_index, note_slug)

    return classification


def main(
    use_ai: bool = False,
    force_files: list[str] | None = None,
    vault: Path = DEFAULT_VAULT,
    personal_vault: Path | None = None,
    source_dir: Path = DEFAULT_RAW_ROOT,
) -> None:
    vp = _vault_paths(vault)
    sp = _source_paths(source_dir)
    exports_dir = sp["perplexity_dir"]
    manifest = vp["perplexity_manifest"]
    processed_index = vp["processed_index"]

    processed = get_processed(manifest)
    existing_notes = get_existing_notes(processed_index)

    # Determine which files to process
    if force_files:
        # --force mode: re-process specific files regardless of manifest
        targets = []
        for name in force_files:
            path = exports_dir / name
            if path.exists():
                targets.append((path, True))
            else:
                print(f"  NOT FOUND: {name}")
        if not targets:
            print("No matching files found.")
            return
    else:
        # Normal mode: new files + changed files (hash mismatch)
        all_exports = sorted(exports_dir.glob("*.md"))
        targets = []
        for f in all_exports:
            if f.name not in processed:
                targets.append((f, False))
            elif processed[f.name] and file_hash(f) != processed[f.name]:
                print(f"  CHANGED : {f.name}")
                targets.append((f, True))

    if not targets:
        print("No new or changed Perplexity exports to process.")
        return

    if not use_ai and not force_files:
        print("Running in local-only mode (no API calls). Use --ai for LLM fallback.\n")

    technical_count = 0
    personal_count = 0
    skipped_count = 0
    changed_count = 0

    for export_file, is_force in targets:
        classification = ingest_file(
            export_file, vault, personal_vault, manifest, processed_index,
            existing_notes, use_ai=use_ai, force=is_force,
        )
        if classification is None:
            print(f"  SKIPPED : {export_file.name}")
            skipped_count += 1
        elif classification == "TECHNICAL":
            label = "UPDATED " if is_force else "TECHNICAL"
            print(f"  {label}: {export_file.name}")
            technical_count += 1
            if is_force:
                changed_count += 1
        else:
            label = "UPDATED " if is_force else "PERSONAL "
            print(f"  {label}: {export_file.name}")
            personal_count += 1
            if is_force:
                changed_count += 1

    print(f"\n=== ingest_sources perplexity summary ===")
    print(f"Files processed: {len(targets)}")
    print(f"  -> Technical vault: {technical_count}")
    print(f"  -> Personal vault:  {personal_count}")
    print(f"  -> Skipped (dup):   {skipped_count}")
    if changed_count:
        print(f"  -> Updated (changed): {changed_count}")

    import sys
    sys.stdout.flush()
    # Regenerate indices in whichever vaults received writes. We import and call
    # rebuild_index directly (not subprocess), so the index regenerator doesn't
    # have to live inside the user's vault directory. In single-vault mode
    # (personal_vault is None), all PERSONAL classifications routed to `vault`.
    import rebuild_index
    if technical_count > 0 or (personal_vault is None and personal_count > 0):
        rebuild_index.main(vault)
    if personal_vault is not None and personal_count > 0:
        rebuild_index.main(personal_vault)


def get_claude_manifest(manifest: Path) -> dict[str, tuple[str, list[str]]]:
    """Parse claude-sessions manifest. Returns {filename: (hash, [slugs])}."""
    if not manifest.exists():
        return {}
    result = {}
    for line in manifest.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        name = parts[0]
        h = parts[1] if len(parts) > 1 else ""
        slugs = parts[2].split(",") if len(parts) > 2 and parts[2] else []
        result[name] = (h, [s for s in slugs if s])
    return result


def write_claude_manifest(
    manifest: Path, entries: dict[str, tuple[str, list[str]]]
) -> None:
    """Overwrite claude-sessions manifest with the given entries."""
    lines = []
    for name in sorted(entries):
        h, slugs = entries[name]
        lines.append(f"{name}\t{h}\t{','.join(sorted(slugs))}")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("\n".join(lines) + ("\n" if lines else ""))


def load_ignore_patterns(path: Path) -> list[str]:
    """Return non-comment, non-empty substring patterns from the ignore file."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line.lower())
    return out


def claude_apply_ignores(
    sessions_dir: Path,
    manifest: Path,
    patterns_file: Path,
) -> list[str]:
    """Empty-mark unprocessed sessions whose content matches any ignore pattern.

    Returns list of newly-ignored filenames. Safe to call repeatedly.
    """
    patterns = load_ignore_patterns(patterns_file)
    if not patterns:
        return []
    entries = get_claude_manifest(manifest)
    newly_ignored: list[str] = []
    for path in sorted(sessions_dir.glob("*.md")):
        if path.name in entries:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        if any(p in content for p in patterns):
            entries[path.name] = (file_hash(path), [])
            newly_ignored.append(path.name)
    if newly_ignored:
        write_claude_manifest(manifest, entries)
    return newly_ignored


def claude_list_unprocessed(
    sessions_dir: Path,
    manifest: Path,
) -> list[Path]:
    """Return raw Claude session files not yet recorded in the manifest."""
    entries = get_claude_manifest(manifest)
    processed = set(entries.keys())
    return sorted(
        f for f in sessions_dir.glob("*.md") if f.name not in processed
    )


def claude_bulk_mark(
    pattern: str,
    sessions_dir: Path,
    manifest: Path,
) -> list[str]:
    """Mark every raw session matching `pattern` (glob) as processed with empty slugs.

    Skips files already in the manifest. Returns the list of newly-marked filenames.
    """
    entries = get_claude_manifest(manifest)
    newly_marked: list[str] = []
    for path in sorted(sessions_dir.glob(pattern)):
        if path.name in entries:
            continue
        entries[path.name] = (file_hash(path), [])
        newly_marked.append(path.name)
    if newly_marked:
        write_claude_manifest(manifest, entries)
    return newly_marked


def claude_mark_processed(
    filename: str,
    slugs: list[str],
    sessions_dir: Path,
    manifest: Path,
) -> None:
    """Record a Claude session as processed, storing hash + produced note slugs."""
    path = sessions_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Raw session not found: {path}")
    entries = get_claude_manifest(manifest)
    h = file_hash(path)
    existing_slugs = entries.get(filename, ("", []))[1]
    merged = sorted(set(existing_slugs) | set(slugs))
    entries[filename] = (h, merged)
    write_claude_manifest(manifest, entries)


def _cmd_perplexity(args: argparse.Namespace) -> None:
    vp = _vault_paths(args.vault)
    vp["manifests"].mkdir(parents=True, exist_ok=True)
    main(
        use_ai=args.ai,
        force_files=args.force,
        vault=args.vault,
        personal_vault=args.personal_vault,
        source_dir=args.source_dir,
    )


def _cmd_claude_session(args: argparse.Namespace) -> None:
    vp = _vault_paths(args.vault)
    sp = _source_paths(args.source_dir)
    vp["manifests"].mkdir(parents=True, exist_ok=True)
    sessions_dir = sp["claude_sessions_dir"]
    manifest = vp["claude_manifest"]
    patterns_file = vp["claude_ignore_patterns"]

    if args.action == "list":
        ignored = claude_apply_ignores(sessions_dir, manifest, patterns_file)
        if ignored:
            print(f"Auto-ignored {len(ignored)} session(s) via ignore patterns:")
            for name in ignored:
                print(f"  IGNORED: {name}")
            print()
        unprocessed = claude_list_unprocessed(sessions_dir, manifest)
        if not unprocessed:
            print("All Claude sessions have been processed.")
            return
        print(f"{len(unprocessed)} unprocessed Claude session(s):")
        for p in unprocessed:
            print(f"  {p.name}")
    elif args.action == "mark":
        slugs = args.slugs.split(",") if args.slugs else []
        slugs = [s.strip() for s in slugs if s.strip()]
        try:
            claude_mark_processed(args.file, slugs, sessions_dir, manifest)
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        suffix = f" (slugs: {', '.join(slugs)})" if slugs else ""
        print(f"MARKED: {args.file}{suffix}")
    elif args.action == "bulk-mark":
        newly = claude_bulk_mark(args.pattern, sessions_dir, manifest)
        print(f"BULK-MARKED {len(newly)} session(s) matching {args.pattern!r}")
        if args.verbose:
            for name in newly:
                print(f"  {name}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified ingest for raw sources into the knowledge vault."
    )
    parser.add_argument(
        "--vault",
        type=lambda s: Path(s).expanduser(),
        default=DEFAULT_VAULT,
        help="Path to the knowledge vault (default: cwd).",
    )
    parser.add_argument(
        "--personal-vault",
        type=lambda s: Path(s).expanduser(),
        default=None,
        help="Optional second vault for PERSONAL-classified notes (dual-vault mode).",
    )
    parser.add_argument(
        "--source-dir",
        type=lambda s: Path(s).expanduser(),
        default=DEFAULT_RAW_ROOT,
        help="Where raw sources live (default: ~/raw-sources).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_perp = sub.add_parser("perplexity", help="Ingest Perplexity exports")
    p_perp.add_argument(
        "--ai", action="store_true",
        help="Use Claude API for ambiguous classification (costs tokens)",
    )
    p_perp.add_argument(
        "--force", nargs="+", metavar="FILE",
        help="Re-process specific export files (by filename)",
    )
    p_perp.set_defaults(func=_cmd_perplexity)

    p_cs = sub.add_parser("claude-session", help="Manage Claude session ingests")
    cs_sub = p_cs.add_subparsers(dest="action", required=True)
    cs_list = cs_sub.add_parser("list", help="List unprocessed sessions")
    cs_list.set_defaults(func=_cmd_claude_session)
    cs_mark = cs_sub.add_parser("mark", help="Mark a session as processed")
    cs_mark.add_argument("file", help="Session filename (e.g. claude-conversation-YYYY-MM-DD-xxx.md)")
    cs_mark.add_argument(
        "--slugs", default="",
        help="Comma-separated list of note slugs this session produced",
    )
    cs_mark.set_defaults(func=_cmd_claude_session)
    cs_bulk = cs_sub.add_parser(
        "bulk-mark",
        help="Mark all sessions matching a glob as processed with empty slugs",
    )
    cs_bulk.add_argument("--pattern", required=True, help="Glob (e.g. '*-agent-*.md')")
    cs_bulk.add_argument("-v", "--verbose", action="store_true")
    cs_bulk.set_defaults(func=_cmd_claude_session)
    return parser


if __name__ == "__main__":
    _args = _build_parser().parse_args()
    _args.func(_args)
