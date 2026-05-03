#!/usr/bin/env python3
"""Semantic cross-linker: finds related notes in a vault and populates related: fields."""

import re
import json
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---', re.DOTALL)
TLDR_RE = re.compile(r'>\s*\*\*TL;DR:\*\*\s*(.+)')
RELATED_RE = re.compile(r'^related:.*$', re.MULTILINE)
WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')

BATCH_SIZE = 80


def parse_frontmatter(content: str) -> dict:
    m = FRONTMATTER_RE.match(content)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            result[key.strip()] = val.strip()
    return result


def get_tldr(content: str) -> str:
    m = TLDR_RE.search(content)
    return m.group(1).strip() if m else ""


def get_existing_related(content: str) -> list[str]:
    """Extract existing [[stem]] links from the related: field."""
    m = RELATED_RE.search(content)
    if not m:
        return []
    return WIKILINK_RE.findall(m.group())


def load_notes(vault: Path) -> list[dict]:
    notes = []
    for path in sorted(vault.glob("*.md")):
        stem = path.stem
        if stem.startswith("moc--") or stem.startswith("_template"):
            continue
        content = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)
        notes.append({
            "path": path,
            "stem": stem,
            "title": fm.get("title", stem),
            "tags": fm.get("tags", "[]"),
            "tldr": get_tldr(content),
        })
    return notes


def build_summary_block(notes: list[dict]) -> str:
    lines = []
    for n in notes:
        desc = n["tldr"] if n["tldr"] else n["title"]
        lines.append(f"- {n['stem']}: {desc}")
    return "\n".join(lines)


def llm_find_related(notes: list[dict], client) -> dict[str, list[str]]:
    """Ask LLM to find related pairs within a batch. Returns {stem: [stems]}."""
    summary = build_summary_block(notes)
    valid_stems = {n["stem"] for n in notes}

    prompt = (
        f"You are analyzing a knowledge vault with {len(notes)} notes. "
        "Find semantically related pairs — notes covering the same topic, technology, "
        "concept, or project from different angles. Include notes where one is a specific "
        "detail of the other, or where linking them would help navigation.\n\n"
        f"Notes:\n{summary}\n\n"
        "Return a JSON object mapping each stem to a list of related stems. "
        "Only include stems that have at least one clear topical match. "
        "Be conservative — only link notes with genuine overlap, not loose associations.\n"
        "Example: {\"stem-a\": [\"stem-b\"], \"stem-b\": [\"stem-a\"]}\n"
        "Return only valid JSON, no explanation."
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    block = message.content[0]
    text = getattr(block, "text", "").strip()
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if not json_match:
        return {}

    raw = json.loads(json_match.group())
    # Filter out stems not in this batch
    return {
        k: [v for v in vs if v in valid_stems and v != k]
        for k, vs in raw.items()
        if k in valid_stems
    }


def merge_related(existing: list[str], new: list[str]) -> list[str]:
    """Merge new stems into existing list without duplicates, preserving order."""
    seen = set(existing)
    result = list(existing)
    for stem in new:
        if stem not in seen:
            seen.add(stem)
            result.append(stem)
    return result


def update_related_field(path: Path, new_stems: list[str]) -> bool:
    """Add new_stems to the related: field. Returns True if file was changed."""
    content = path.read_text(encoding="utf-8")
    existing = get_existing_related(content)
    merged = merge_related(existing, new_stems)

    if set(merged) == set(existing):
        return False

    links = ", ".join(f"[[{s}]]" for s in merged)
    new_line = f"related: {links}" if links else "related: []"
    updated = RELATED_RE.sub(new_line, content)
    path.write_text(updated, encoding="utf-8")
    return True


def run(vault: Path) -> None:
    import anthropic
    client = anthropic.Anthropic()

    print(f"Loading notes from {vault}...")
    notes = load_notes(vault)
    print(f"  {len(notes)} notes found")

    # Split into batches
    batches = [notes[i:i + BATCH_SIZE] for i in range(0, len(notes), BATCH_SIZE)]

    all_related: dict[str, list[str]] = {}

    for i, batch in enumerate(batches):
        print(f"  Batch {i + 1}/{len(batches)}: finding related pairs ({len(batch)} notes)...")
        batch_result = llm_find_related(batch, client)
        for stem, related in batch_result.items():
            if stem not in all_related:
                all_related[stem] = []
            all_related[stem] = merge_related(all_related[stem], related)

    # Also do a cross-batch pass if there are multiple batches
    if len(batches) > 1:
        print(f"  Cross-batch pass ({len(notes)} notes)...")
        cross_result = llm_find_related(notes, client)
        for stem, related in cross_result.items():
            if stem not in all_related:
                all_related[stem] = []
            all_related[stem] = merge_related(all_related[stem], related)

    # Apply updates
    stem_to_path = {n["stem"]: n["path"] for n in notes}
    updated = 0
    links_added = 0

    for stem, related_stems in all_related.items():
        if stem not in stem_to_path or not related_stems:
            continue
        before = get_existing_related(stem_to_path[stem].read_text(encoding="utf-8"))
        changed = update_related_field(stem_to_path[stem], related_stems)
        if changed:
            after = get_existing_related(stem_to_path[stem].read_text(encoding="utf-8"))
            updated += 1
            links_added += len(after) - len(before)

    print(f"\n=== link_notes summary ===")
    print(f"Notes updated: {updated}")
    print(f"Links added:   {links_added}")


def main() -> None:
    if len(sys.argv) > 1:
        vault = Path(sys.argv[1]).expanduser()
    else:
        vault = Path.cwd()
    run(vault)


if __name__ == "__main__":
    main()
