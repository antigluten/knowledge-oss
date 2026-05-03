import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import link_notes as ln


# --- parse / load helpers ---

def test_get_existing_related_empty():
    content = "---\ntitle: Test\nrelated: []\n---\n"
    assert ln.get_existing_related(content) == []


def test_get_existing_related_with_links():
    content = "---\ntitle: Test\nrelated: [[concept--a]], [[concept--b]]\n---\n"
    result = ln.get_existing_related(content)
    assert "concept--a" in result
    assert "concept--b" in result



def test_get_tldr_present():
    content = "> **TL;DR:** Swift concurrency model overview.\n"
    assert ln.get_tldr(content) == "Swift concurrency model overview."


def test_get_tldr_missing():
    assert ln.get_tldr("No tldr here") == ""


def test_load_notes_skips_mocs(tmp_path):
    (tmp_path / "concept--foo.md").write_text(
        "---\ntitle: Foo\ntags: [ios]\nrelated: []\n---\n> **TL;DR:** Foo.\n"
    )
    (tmp_path / "moc--index.md").write_text("---\ntitle: MOC\n---\n")
    notes = ln.load_notes(tmp_path)
    stems = [n["stem"] for n in notes]
    assert "concept--foo" in stems
    assert "moc--index" not in stems


def test_load_notes_extracts_fields(tmp_path):
    (tmp_path / "concept--bar.md").write_text(
        "---\ntitle: Bar Note\ntags: [backend]\nrelated: []\n---\n> **TL;DR:** A bar.\n"
    )
    notes = ln.load_notes(tmp_path)
    assert notes[0]["title"] == "Bar Note"
    assert notes[0]["tldr"] == "A bar."
    assert notes[0]["stem"] == "concept--bar"


# --- merge_related ---

def test_merge_related_no_duplicates():
    result = ln.merge_related(["a", "b"], ["b", "c"])
    assert result == ["a", "b", "c"]


def test_merge_related_preserves_order():
    result = ln.merge_related(["c", "a"], ["b"])
    assert result == ["c", "a", "b"]


def test_merge_related_empty_existing():
    assert ln.merge_related([], ["a", "b"]) == ["a", "b"]


def test_merge_related_empty_new():
    assert ln.merge_related(["a"], []) == ["a"]


# --- update_related_field ---

def test_update_related_field_adds_links(tmp_path):
    p = tmp_path / "note.md"
    p.write_text("---\ntitle: Test\nrelated: []\n---\nContent.\n")
    changed = ln.update_related_field(p, ["concept--foo", "concept--bar"])
    assert changed is True
    result = p.read_text()
    assert "[[concept--foo]]" in result
    assert "[[concept--bar]]" in result


def test_update_related_field_no_change_when_already_present(tmp_path):
    p = tmp_path / "note.md"
    p.write_text("---\ntitle: Test\nrelated: [[concept--foo]]\n---\nContent.\n")
    changed = ln.update_related_field(p, ["concept--foo"])
    assert changed is False
    assert "[[concept--foo]]" in p.read_text()


def test_update_related_field_merges_without_removing(tmp_path):
    p = tmp_path / "note.md"
    p.write_text("---\ntitle: Test\nrelated: [[concept--existing]]\n---\nContent.\n")
    ln.update_related_field(p, ["concept--new"])
    result = p.read_text()
    assert "[[concept--existing]]" in result
    assert "[[concept--new]]" in result


# --- llm_find_related (mocked) ---

def test_llm_find_related_returns_valid_pairs(monkeypatch):
    notes = [
        {"stem": "concept--swift-actors", "title": "Swift Actors", "tldr": "Actor isolation in Swift.", "tags": "[ios]"},
        {"stem": "concept--swift-async", "title": "Swift Async/Await", "tldr": "Async functions in Swift.", "tags": "[ios]"},
        {"stem": "concept--diet-guide", "title": "Diet Guide", "tldr": "Mediterranean diet basics.", "tags": "[lifestyle]"},
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text='{"concept--swift-actors": ["concept--swift-async"], "concept--swift-async": ["concept--swift-actors"]}')
    ]
    result = ln.llm_find_related(notes, mock_client)
    assert "concept--swift-actors" in result
    assert "concept--swift-async" in result["concept--swift-actors"]
    assert "concept--diet-guide" not in result


def test_llm_find_related_filters_unknown_stems(monkeypatch):
    notes = [
        {"stem": "concept--a", "title": "A", "tldr": "Note A.", "tags": "[]"},
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text='{"concept--a": ["concept--nonexistent"]}')
    ]
    result = ln.llm_find_related(notes, mock_client)
    assert result.get("concept--a", []) == []


def test_llm_find_related_handles_bad_json(monkeypatch):
    notes = [{"stem": "concept--a", "title": "A", "tldr": "A.", "tags": "[]"}]
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text="Sorry, I cannot help with that.")
    ]
    result = ln.llm_find_related(notes, mock_client)
    assert result == {}


def test_llm_find_related_excludes_self_links():
    notes = [
        {"stem": "concept--a", "title": "A", "tldr": "Note A.", "tags": "[]"},
        {"stem": "concept--b", "title": "B", "tldr": "Note B.", "tags": "[]"},
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [
        MagicMock(text='{"concept--a": ["concept--a", "concept--b"]}')
    ]
    result = ln.llm_find_related(notes, mock_client)
    assert "concept--a" not in result.get("concept--a", [])
    assert "concept--b" in result.get("concept--a", [])
