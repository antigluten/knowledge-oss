#!/usr/bin/env python3
"""Rebuild MOC files and Master Index from existing vault notes."""

import re
from pathlib import Path
from collections import defaultdict

FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---', re.DOTALL)
TLDR_RE = re.compile(r'>\s*\*\*TL;DR:\*\*\s*(.+)')
WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')
FENCED_CODE_RE = re.compile(r'```.*?```', re.DOTALL)
INLINE_CODE_RE = re.compile(r'`[^`\n]+`')


def strip_code_blocks(content: str) -> str:
    """Remove fenced code blocks and inline code spans so wikilink scanning ignores code examples."""
    content = FENCED_CODE_RE.sub('', content)
    content = INLINE_CODE_RE.sub('', content)
    return content


def parse_frontmatter(content: str) -> dict:
    """Return frontmatter key-value dict or {} if none found."""
    m = FRONTMATTER_RE.match(content)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            val = val.strip()
            # Strip matched surrounding YAML quotes ("..." or '...').
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            result[key.strip()] = val
    return result


def get_tldr(content: str) -> str:
    """Return TL;DR text or empty string."""
    m = TLDR_RE.search(content)
    return m.group(1).strip() if m else ""


def scan_notes(vault: Path) -> list[dict]:
    """Return list of note dicts for all content *.md files (no templates, no MOCs)."""
    notes = []
    for path in sorted(vault.glob("*.md")):
        stem = path.stem
        if (
            stem.startswith("_template")
            or stem.startswith("moc--")
            or stem in ("log", "CLAUDE", "README")
        ):
            continue
        content = path.read_text()
        if not content.strip():
            # Zero-byte or whitespace-only stub — skip so it doesn't pollute MOCs/glossary
            continue
        fm = parse_frontmatter(content)
        notes.append({
            "path": path,
            "stem": stem,
            "title": fm.get("title", stem),
            "tags": fm.get("tags", "[]"),
            "session_file": fm.get("session_file", ""),
            "tldr": get_tldr(content),
            "content": content,
        })
    return notes


def _link_target(link: str) -> str:
    """Strip Obsidian's [[stem|display]] pipe syntax to just the stem."""
    return link.split("|", 1)[0].split("#", 1)[0].strip()


def count_wikilinks(notes: list[dict]) -> dict[str, int]:
    """Count how many times each [[wikilink]] target is referenced across all notes."""
    counts: dict[str, int] = defaultdict(int)
    for note in notes:
        for link in WIKILINK_RE.findall(strip_code_blocks(note["content"])):
            counts[_link_target(link)] += 1
    return dict(counts)


def find_broken_links(notes: list[dict], vault: Path) -> list[str]:
    """Return list of 'note_stem: [[target]]' strings for wikilinks pointing to missing files."""
    stems = {n["stem"] for n in notes}
    broken = []
    for note in notes:
        for link in WIKILINK_RE.findall(strip_code_blocks(note["content"])):
            target = _link_target(link)
            if target not in stems and not (vault / f"{target}.md").exists():
                broken.append(f"{note['stem']}: [[{link}]]")
    return broken


def _note_line(note: dict) -> str:
    desc = note["tldr"] if note["tldr"] else note["title"]
    return f"- [[{note['stem']}]] — {desc}"


def build_moc(title: str, prefixes: list[str], notes: list[dict], date: str) -> str:
    """Build MOC markdown for notes matching any of the given prefixes."""
    matching = [n for n in notes if any(n["stem"].startswith(p) for p in prefixes)]
    lines = [
        "---",
        f"title: {title}",
        "tags: [moc, index]",
        f"created: {date}",
        "---",
        "",
        f"# {title}",
        "",
    ]
    if matching:
        for n in matching:
            lines.append(_note_line(n))
    else:
        lines.append("_No notes yet._")
    return "\n".join(lines) + "\n"


def build_master_index(notes: list[dict], link_counts: dict[str, int], date: str) -> str:
    """Build the master index MOC with domain links and top linked concepts."""
    top = sorted(link_counts.items(), key=lambda x: -x[1])[:10]

    lines = [
        "---",
        "title: Master Index",
        "tags: [moc, index]",
        f"created: {date}",
        "---",
        "",
        "# DevKnowledge Master Index",
        "",
        "> Knowledge base built from Claude Code sessions.",
        f"> Last updated: {date}",
        "",
        "## By Domain",
        "",
        "- [[moc--architecture]] — system decisions, patterns, trade-offs",
        "- [[moc--development]] — code snippets, workflows, configs",
        "- [[moc--debugging]] — issues, root causes, fixes",
        "- [[moc--tools]] — every tool referenced",
        "- [[moc--concepts]] — atomic concept definitions",
        "- [[moc--synthesis]] — cross-note syntheses and query answers",
        "- [[moc--projects]] — notes grouped by project",
        "- [[glossary]] — A–Z term index (concepts, patterns, decisions, bugs, tools)",
        "",
        "## Top Linked Concepts",
        "",
    ]
    if top:
        for stem, count in top:
            lines.append(f"- [[{stem}]] ({count} reference{'s' if count != 1 else ''})")
    else:
        lines.append("_No links yet._")

    lines += ["", "## Stats", "", f"- Total notes: {len(notes)}"]
    return "\n".join(lines) + "\n"


def build_projects_moc(notes: list[dict], date: str) -> str:
    """Build MOC grouping notes by detected project from session_file."""
    # Map session-file stems (or stem prefixes) to a project label so notes
    # produced by the same Claude session group together in this MOC.
    # Customize for your own vault — entries below are illustrative.
    # Example:
    #     "2026-03-27-249abd03": "iOS",
    #     "2026-04-02":          "Backend",
    PROJECT_MAP: dict[str, str] = {}

    buckets: dict[str, list[dict]] = defaultdict(list)
    for note in notes:
        sf = note["session_file"]
        project = "Uncategorized"
        for key, name in PROJECT_MAP.items():
            if key in sf:
                project = name
                break
        buckets[project].append(note)

    lines = [
        "---",
        "title: Projects MOC",
        "tags: [moc, index]",
        f"created: {date}",
        "---",
        "",
        "# Projects MOC",
        "",
    ]
    for project in sorted(buckets):
        lines.append(f"## {project}")
        lines.append("")
        for n in buckets[project]:
            lines.append(_note_line(n))
        lines.append("")
    return "\n".join(lines) + "\n"


MOC_SPECS = [
    ("moc--architecture.md",  "Architecture",  ["arch-decision--", "arch-pattern--", "arch-system--"]),
    ("moc--development.md",   "Development",   ["dev-snippet--", "dev-workflow--", "dev-config--"]),
    ("moc--debugging.md",     "Debugging",     ["bug-issue--", "bug-pattern--"]),
    ("moc--tools.md",         "Tools",         ["tool--"]),
    ("moc--concepts.md",      "Concepts",      ["concept--"]),
    ("moc--synthesis.md",     "Synthesis",     ["synthesis--"]),
]

GLOSSARY_PREFIXES = (
    "concept--",
    "arch-pattern--",
    "arch-system--",
    "arch-decision--",
    "bug-pattern--",
    "tool--",
)

LEADING_ARTICLE_RE = re.compile(r'^(the|a|an)\s+', re.IGNORECASE)


def _glossary_sort_key(title: str) -> str:
    return LEADING_ARTICLE_RE.sub("", title).lower()


def _glossary_letter(title: str) -> str:
    key = _glossary_sort_key(title)
    if not key:
        return "#"
    first = key[0].upper()
    return first if first.isalpha() else "0-9"


def build_glossary(notes: list[dict], date: str) -> str:
    """Build glossary.md — A-Z term index covering concepts, patterns, decisions, systems, bug-patterns, tools."""
    entries = [n for n in notes if any(n["stem"].startswith(p) for p in GLOSSARY_PREFIXES)]
    entries.sort(key=lambda n: _glossary_sort_key(n["title"]))

    lines = [
        "---",
        "title: Glossary",
        "tags: [moc, index, glossary]",
        f"created: {date}",
        "---",
        "",
        "# Glossary",
        "",
        "> A–Z index of every named term in this vault — concepts, architecture patterns,"
        " architecture decisions, systems, bug patterns, and tools. Each entry links to"
        " the home note where the term is explained.",
        "> Auto-regenerated by `rebuild_index.py`.",
        "",
    ]

    buckets: dict[str, list[dict]] = defaultdict(list)
    for note in entries:
        buckets[_glossary_letter(note["title"])].append(note)

    # Sort letters with "0-9" first, then A..Z alphabetically.
    def letter_sort(letter: str) -> tuple[int, str]:
        return (0, "") if letter == "0-9" else (1, letter)

    for letter in sorted(buckets.keys(), key=letter_sort):
        lines.append(f"## {letter}")
        lines.append("")
        for note in buckets[letter]:
            definition = note["tldr"] or "_No TL;DR yet._"
            lines.append(f"**{note['title']}** — {definition} See [[{note['stem']}]].")
            lines.append("")

    lines += [f"---", "", f"_Total terms: {len(entries)}_", ""]
    return "\n".join(lines) + "\n"


def main(vault: Path | None = None, date: str | None = None) -> None:
    if vault is None:
        vault = Path.cwd()
    if date is None:
        from datetime import date as _dt
        date = _dt.today().isoformat()
    notes = scan_notes(vault)
    link_counts = count_wikilinks(notes)
    broken = find_broken_links(notes, vault)

    for filename, title, prefixes in MOC_SPECS:
        (vault / filename).write_text(build_moc(title, prefixes, notes, date))

    (vault / "moc--projects.md").write_text(build_projects_moc(notes, date))
    (vault / "moc--master-index.md").write_text(build_master_index(notes, link_counts, date))
    (vault / "glossary.md").write_text(build_glossary(notes, date))

    glossary_terms = sum(
        1 for n in notes if any(n["stem"].startswith(p) for p in GLOSSARY_PREFIXES)
    )
    print(f"\n=== rebuild_index summary ({date}) ===")
    print(f"Notes scanned:   {len(notes)}")
    print(f"MOC files:       {len(MOC_SPECS) + 2}")
    print(f"Glossary terms:  {glossary_terms}")
    print(f"Broken links:    {len(broken)}")
    if broken:
        print("\nBroken links found:")
        for b in broken:
            print(f"  WARNING: {b}")
    print()


if __name__ == "__main__":
    import sys
    vault_arg = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else None
    main(vault_arg)
