import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import rebuild_index as ri

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_frontmatter_extracts_title():
    content = (FIXTURES / "concept--test-fixture.md").read_text()
    fm = ri.parse_frontmatter(content)
    assert fm["title"] == "Test Concept"


def test_parse_frontmatter_extracts_tags():
    content = (FIXTURES / "concept--test-fixture.md").read_text()
    fm = ri.parse_frontmatter(content)
    assert fm["tags"] == "[systems, concept, mature]"


def test_parse_frontmatter_extracts_session_file():
    content = (FIXTURES / "concept--test-fixture.md").read_text()
    fm = ri.parse_frontmatter(content)
    assert fm["session_file"] == "claude-conversation-2026-03-27-249abd03.md"


def test_parse_frontmatter_returns_empty_for_missing():
    fm = ri.parse_frontmatter("# No frontmatter here\n\nJust content.")
    assert fm == {}


def test_get_tldr_extracts_text():
    content = (FIXTURES / "concept--test-fixture.md").read_text()
    assert ri.get_tldr(content) == "A fixture concept used in unit tests."


def test_get_tldr_returns_empty_for_missing():
    assert ri.get_tldr("# No TL;DR\n\nJust content.") == ""


def test_scan_notes_returns_all_non_template_non_moc(tmp_path):
    import shutil
    for f in FIXTURES.glob("*.md"):
        shutil.copy(f, tmp_path / f.name)
    (tmp_path / "_template--ignore-me.md").write_text("---\ntitle: Template\n---\n")
    (tmp_path / "moc--index.md").write_text("---\ntitle: MOC\n---\n")

    notes = ri.scan_notes(tmp_path)
    stems = [n["stem"] for n in notes]
    assert "_template--ignore-me" not in stems
    assert "moc--index" not in stems
    assert "concept--test-fixture" in stems
    assert "dev-snippet--test-snippet" in stems
    assert "tool--test-tool" in stems
    assert "arch-decision--test-decision" in stems
    assert "_template--ignore-me" not in stems
    assert "moc--index" not in stems


def test_scan_notes_extracts_title_and_tldr(tmp_path):
    import shutil
    shutil.copy(FIXTURES / "concept--test-fixture.md", tmp_path / "concept--test-fixture.md")
    notes = ri.scan_notes(tmp_path)
    assert notes[0]["title"] == "Test Concept"
    assert notes[0]["tldr"] == "A fixture concept used in unit tests."


def test_count_wikilinks_counts_references():
    notes = [
        {"content": "See [[concept--test-fixture]] and [[tool--test-tool]].", "stem": "a"},
        {"content": "Also [[concept--test-fixture]] again.", "stem": "b"},
    ]
    counts = ri.count_wikilinks(notes)
    assert counts["concept--test-fixture"] == 2
    assert counts["tool--test-tool"] == 1


def test_count_wikilinks_empty():
    counts = ri.count_wikilinks([{"content": "No links here.", "stem": "a"}])
    assert counts == {}


def test_find_broken_links_detects_missing(tmp_path):
    import shutil
    for f in FIXTURES.glob("*.md"):
        shutil.copy(f, tmp_path / f.name)
    notes = ri.scan_notes(tmp_path)
    broken = ri.find_broken_links(notes, tmp_path)
    # tool--test-tool.md links to concept--nonexistent-broken-link which doesn't exist
    assert any("concept--nonexistent-broken-link" in b for b in broken)


def test_find_broken_links_no_false_positives(tmp_path):
    import shutil
    for f in FIXTURES.glob("*.md"):
        shutil.copy(f, tmp_path / f.name)
    notes = ri.scan_notes(tmp_path)
    broken = ri.find_broken_links(notes, tmp_path)
    # concept--test-fixture exists, must not appear as broken
    assert not any("concept--test-fixture" in b for b in broken)


def test_build_moc_includes_matching_notes(tmp_path):
    import shutil
    for f in FIXTURES.glob("*.md"):
        shutil.copy(f, tmp_path / f.name)
    notes = ri.scan_notes(tmp_path)
    moc = ri.build_moc("Development", ["dev-snippet--", "dev-workflow--", "dev-config--"], notes, "2026-04-03")
    assert "dev-snippet--test-snippet" in moc
    assert "arch-decision--test-decision" not in moc


def test_build_moc_shows_empty_message_when_no_notes():
    moc = ri.build_moc("Empty Domain", ["dev-workflow--"], [], "2026-04-03")
    assert "_No notes yet._" in moc


def test_build_master_index_contains_domain_links(tmp_path):
    import shutil
    for f in FIXTURES.glob("*.md"):
        shutil.copy(f, tmp_path / f.name)
    notes = ri.scan_notes(tmp_path)
    counts = ri.count_wikilinks(notes)
    idx = ri.build_master_index(notes, counts, date="2026-04-03")
    assert "[[moc--architecture]]" in idx
    assert "[[moc--development]]" in idx
    assert "[[moc--debugging]]" in idx
    assert "[[moc--tools]]" in idx
    assert "[[moc--concepts]]" in idx


def test_build_master_index_shows_top_concepts(tmp_path):
    import shutil
    for f in FIXTURES.glob("*.md"):
        shutil.copy(f, tmp_path / f.name)
    notes = ri.scan_notes(tmp_path)
    counts = ri.count_wikilinks(notes)
    idx = ri.build_master_index(notes, counts, date="2026-04-03")
    # concept--test-fixture is referenced by both concept and arch-decision fixtures
    assert "concept--test-fixture" in idx


def test_main_writes_moc_files(tmp_path):
    import shutil
    for f in FIXTURES.glob("*.md"):
        shutil.copy(f, tmp_path / f.name)
    ri.main(vault=tmp_path, date="2026-04-03")
    assert (tmp_path / "moc--master-index.md").exists()
    assert (tmp_path / "moc--architecture.md").exists()
    assert (tmp_path / "moc--development.md").exists()
    assert (tmp_path / "moc--debugging.md").exists()
    assert (tmp_path / "moc--tools.md").exists()
    assert (tmp_path / "moc--concepts.md").exists()
    assert (tmp_path / "moc--projects.md").exists()
