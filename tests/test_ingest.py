import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import ingest_sources as ip

FIXTURES = Path(__file__).parent / "fixtures"


def test_keyword_classify_technical_english():
    assert ip.keyword_classify("Swift Concurrency Guide", "async await actors swift protocol struct class") == "TECHNICAL"


def test_keyword_classify_personal_english():
    assert ip.keyword_classify("Mediterranean Diet", "health nutrition food recipe fitness sleep") == "PERSONAL"


def test_keyword_classify_technical_russian():
    assert ip.keyword_classify("Алгоритмы сортировки", "алгоритм программирование код функция класс") == "TECHNICAL"


def test_keyword_classify_personal_russian():
    assert ip.keyword_classify("Здоровое питание", "здоровье питание еда рецепт тренировка") == "PERSONAL"


def test_keyword_classify_ambiguous_returns_ambiguous():
    assert ip.keyword_classify("General Notes", "some random content with no domain keywords at all") == "AMBIGUOUS"


def test_keyword_classify_tie_returns_ambiguous():
    assert ip.keyword_classify("Mixed", "swift health python fitness") == "AMBIGUOUS"


def test_get_processed_returns_empty_when_no_manifest(tmp_path):
    manifest = tmp_path / ".perplexity_ingested.txt"
    assert ip.get_processed(manifest) == {}


def test_get_processed_returns_filenames(tmp_path):
    manifest = tmp_path / ".perplexity_ingested.txt"
    manifest.write_text("file-a.md\nfile-b.md\n")
    result = ip.get_processed(manifest)
    assert "file-a.md" in result
    assert "file-b.md" in result


def test_get_processed_returns_hashes(tmp_path):
    manifest = tmp_path / ".perplexity_ingested.txt"
    manifest.write_text("file-a.md\tabc123\nfile-b.md\tdef456\n")
    result = ip.get_processed(manifest)
    assert result["file-a.md"] == "abc123"
    assert result["file-b.md"] == "def456"


def test_get_processed_handles_mixed_format(tmp_path):
    manifest = tmp_path / ".perplexity_ingested.txt"
    manifest.write_text("old-file.md\nnew-file.md\tabc123\n")
    result = ip.get_processed(manifest)
    assert result["old-file.md"] == ""
    assert result["new-file.md"] == "abc123"


def test_mark_processed_creates_manifest_with_hash(tmp_path):
    manifest = tmp_path / ".perplexity_ingested.txt"
    ip.mark_processed(manifest, "file-a.md", "abc123")
    assert manifest.read_text() == "file-a.md\tabc123\n"


def test_mark_processed_appends(tmp_path):
    manifest = tmp_path / ".perplexity_ingested.txt"
    ip.mark_processed(manifest, "file-a.md", "abc123")
    ip.mark_processed(manifest, "file-b.md", "def456")
    result = ip.get_processed(manifest)
    assert "file-a.md" in result
    assert "file-b.md" in result


def test_extract_title_from_h1():
    content = "# My Research Title\n\nSome content here."
    assert ip.extract_title(content, "some-file.md") == "My Research Title"


def test_extract_title_falls_back_to_filename():
    content = "No heading here, just content."
    assert ip.extract_title(content, "swift-concurrency-guide.md") == "Swift Concurrency Guide"


def test_slugify_basic():
    assert ip.slugify("OpenTelemetry Spans and Traces") == "opentelemetry-spans-and-traces"


def test_slugify_max_six_words():
    assert ip.slugify("One Two Three Four Five Six Seven Eight") == "one-two-three-four-five-six"


def test_slugify_strips_punctuation():
    assert ip.slugify("Swift's Concurrency Model (async/await)") == "swifts-concurrency-model-asyncawait"


def test_detect_lang_russian():
    assert ip.detect_lang("Это текст на русском языке для тестирования") == "ru"


def test_detect_lang_english():
    assert ip.detect_lang("This is English content about programming") == "en"


def test_detect_lang_mixed_defaults_to_ru():
    assert ip.detect_lang("Hello мир — mixed content") == "ru"


def test_build_note_technical_returns_correct_prefix():
    _, filename = ip.build_note(
        title="Swift Concurrency",
        content="Content about async await",
        filename="perplexity-swift.md",
        classification="TECHNICAL",
    )
    assert filename.startswith("concept--")


def test_build_note_personal_returns_correct_prefix():
    _, filename = ip.build_note(
        title="Mediterranean Diet",
        content="Content about food and health",
        filename="perplexity-diet.md",
        classification="PERSONAL",
    )
    assert filename.startswith("concept--")


def test_build_note_contains_required_frontmatter():
    content, _ = ip.build_note(
        title="Test Note",
        content="Some content",
        filename="perplexity-test.md",
        classification="TECHNICAL",
    )
    assert "source: perplexity" in content
    assert "session_file: perplexity-test.md" in content
    assert "title: Test Note" in content


def test_build_note_detects_russian_lang():
    content, _ = ip.build_note(
        title="Здоровье",
        content="Текст о здоровье и питании",
        filename="perplexity-health-ru.md",
        classification="PERSONAL",
    )
    assert "lang: ru" in content


def test_build_note_english_lang():
    content, _ = ip.build_note(
        title="Swift Guide",
        content="Content about programming in English",
        filename="perplexity-swift.md",
        classification="TECHNICAL",
    )
    assert "lang: en" in content


def test_build_note_slug_in_filename():
    _, filename = ip.build_note(
        title="OpenTelemetry Swift Integration",
        content="Content",
        filename="perplexity-otel.md",
        classification="TECHNICAL",
    )
    assert filename == "concept--opentelemetry-swift-integration.md"


from unittest.mock import patch, MagicMock


def test_llm_classify_returns_technical(monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="TECHNICAL")]
    monkeypatch.setattr("ingest_sources._anthropic_client", lambda: mock_client)
    result = ip.llm_classify("Some title", "Some content")
    assert result == "TECHNICAL"


def test_llm_classify_returns_personal(monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="PERSONAL")]
    monkeypatch.setattr("ingest_sources._anthropic_client", lambda: mock_client)
    result = ip.llm_classify("Some title", "Some content")
    assert result == "PERSONAL"


def test_llm_classify_defaults_personal_on_unknown(monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="UNKNOWN")]
    monkeypatch.setattr("ingest_sources._anthropic_client", lambda: mock_client)
    result = ip.llm_classify("Some title", "Some content")
    assert result == "PERSONAL"


def test_classify_skips_llm_when_clear_technical():
    with patch("ingest_sources.llm_classify") as mock_llm:
        result = ip.classify("Swift Protocol Guide", "swift protocol struct class async await function")
        mock_llm.assert_not_called()
    assert result == "TECHNICAL"


def test_classify_defaults_to_technical_when_ambiguous_no_ai():
    result = ip.classify("General Notes", "some random content with no keywords", use_ai=False)
    assert result == "TECHNICAL"


def test_classify_calls_llm_when_ambiguous_with_ai(monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="PERSONAL")]
    monkeypatch.setattr("ingest_sources._anthropic_client", lambda: mock_client)
    result = ip.classify("General Notes", "some random content with no keywords", use_ai=True)
    assert result == "PERSONAL"


def test_ingest_file_technical_goes_to_dev_vault(tmp_path):
    vault = tmp_path / "knowledge"
    personal_vault = tmp_path / "personal"
    vault.mkdir()
    personal_vault.mkdir()
    manifest = tmp_path / ".manifest.txt"
    processed_index = tmp_path / ".processed_notes.txt"

    export = FIXTURES / "perplexity-swift-concurrency.md"
    result = ip.ingest_file(export, vault, personal_vault, manifest, processed_index)

    assert result == "TECHNICAL"
    assert any(vault.glob("concept--*.md"))
    assert not any(personal_vault.glob("*.md"))
    assert export.name in manifest.read_text()


def test_ingest_file_personal_goes_to_personal_vault(tmp_path):
    vault = tmp_path / "knowledge"
    personal_vault = tmp_path / "personal"
    vault.mkdir()
    personal_vault.mkdir()
    manifest = tmp_path / ".manifest.txt"
    processed_index = tmp_path / ".processed_notes.txt"

    export = FIXTURES / "perplexity-mediterranean-diet.md"
    result = ip.ingest_file(export, vault, personal_vault, manifest, processed_index)

    assert result == "PERSONAL"
    assert any(personal_vault.glob("concept--*.md"))
    assert not any(vault.glob("*.md"))


def test_ingest_file_russian_personal(tmp_path):
    vault = tmp_path / "knowledge"
    personal_vault = tmp_path / "personal"
    vault.mkdir()
    personal_vault.mkdir()
    manifest = tmp_path / ".manifest.txt"
    processed_index = tmp_path / ".processed_notes.txt"

    export = FIXTURES / "perplexity-zdorovye-ru.md"
    result = ip.ingest_file(export, vault, personal_vault, manifest, processed_index)

    assert result == "PERSONAL"
    notes = list(personal_vault.glob("concept--*.md"))
    assert len(notes) == 1
    assert "lang: ru" in notes[0].read_text()


def test_claude_manifest_roundtrip(tmp_path):
    manifest = tmp_path / "claude-sessions.txt"
    entries = {
        "claude-conversation-a.md": ("abc123", ["concept--foo", "tool--bar"]),
        "claude-conversation-b.md": ("", []),
    }
    ip.write_claude_manifest(manifest, entries)
    parsed = ip.get_claude_manifest(manifest)
    assert parsed["claude-conversation-a.md"] == ("abc123", ["concept--foo", "tool--bar"])
    assert parsed["claude-conversation-b.md"] == ("", [])


def test_claude_list_unprocessed(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "claude-conversation-a.md").write_text("# A")
    (sessions / "claude-conversation-b.md").write_text("# B")
    (sessions / "claude-conversation-c.md").write_text("# C")
    manifest = tmp_path / "claude-sessions.txt"
    ip.write_claude_manifest(manifest, {"claude-conversation-b.md": ("h", [])})
    unprocessed = ip.claude_list_unprocessed(sessions, manifest)
    names = [p.name for p in unprocessed]
    assert names == ["claude-conversation-a.md", "claude-conversation-c.md"]


def test_claude_mark_processed_records_hash_and_slugs(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    raw = sessions / "claude-conversation-x.md"
    raw.write_text("# session content")
    manifest = tmp_path / "claude-sessions.txt"
    ip.claude_mark_processed(
        "claude-conversation-x.md", ["concept--a", "tool--b"],
        sessions_dir=sessions, manifest=manifest,
    )
    entries = ip.get_claude_manifest(manifest)
    assert "claude-conversation-x.md" in entries
    h, slugs = entries["claude-conversation-x.md"]
    assert h == ip.file_hash(raw)
    assert slugs == ["concept--a", "tool--b"]


def test_claude_mark_processed_merges_slugs_on_reprocess(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "claude-conversation-x.md").write_text("# content")
    manifest = tmp_path / "claude-sessions.txt"
    ip.claude_mark_processed(
        "claude-conversation-x.md", ["concept--a"],
        sessions_dir=sessions, manifest=manifest,
    )
    ip.claude_mark_processed(
        "claude-conversation-x.md", ["tool--b"],
        sessions_dir=sessions, manifest=manifest,
    )
    _, slugs = ip.get_claude_manifest(manifest)["claude-conversation-x.md"]
    assert slugs == ["concept--a", "tool--b"]


def test_claude_bulk_mark_matches_glob_and_skips_existing(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "claude-conversation-2026-04-09-agent-a1.md").write_text("a1")
    (sessions / "claude-conversation-2026-04-09-agent-a2.md").write_text("a2")
    (sessions / "claude-conversation-2026-04-09-main.md").write_text("main")
    manifest = tmp_path / "claude-sessions.txt"
    # Pre-mark one of the agent files to confirm bulk skips existing entries.
    ip.claude_mark_processed(
        "claude-conversation-2026-04-09-agent-a1.md", ["existing--slug"],
        sessions_dir=sessions, manifest=manifest,
    )

    newly = ip.claude_bulk_mark(
        "*-agent-*.md", sessions_dir=sessions, manifest=manifest,
    )

    assert newly == ["claude-conversation-2026-04-09-agent-a2.md"]
    entries = ip.get_claude_manifest(manifest)
    # Pre-existing entry preserved with its slugs.
    assert entries["claude-conversation-2026-04-09-agent-a1.md"][1] == ["existing--slug"]
    # Newly-marked entry has a hash and empty slugs.
    h, slugs = entries["claude-conversation-2026-04-09-agent-a2.md"]
    assert h and slugs == []
    # Main file left alone.
    assert "claude-conversation-2026-04-09-main.md" not in entries


def test_claude_mark_processed_raises_if_raw_missing(tmp_path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    manifest = tmp_path / "claude-sessions.txt"
    import pytest
    with pytest.raises(FileNotFoundError):
        ip.claude_mark_processed(
            "missing.md", [], sessions_dir=sessions, manifest=manifest,
        )


def test_main_skips_already_processed(tmp_path):
    vault = tmp_path / "knowledge"
    personal_vault = tmp_path / "personal"
    source_dir = tmp_path / "raw-sources"
    exports_dir = source_dir / "perplexity"
    vault.mkdir()
    personal_vault.mkdir()
    exports_dir.mkdir(parents=True)
    manifests_dir = vault / ".manifests"
    manifests_dir.mkdir()
    manifest = manifests_dir / "perplexity.txt"

    import shutil
    shutil.copy(FIXTURES / "perplexity-swift-concurrency.md", exports_dir)

    manifest.write_text("perplexity-swift-concurrency.md\n")

    ip.main(vault=vault, personal_vault=personal_vault, source_dir=source_dir)

    assert not any(vault.glob("*.md"))


# ----- authorship marker tests (spec: 2026-05-02-personal-vault-note-pipeline-design.md) -----


def test_build_note_personal_includes_authored_by_frontmatter():
    note_content, _ = ip.build_note(
        title="Mediterranean Diet",
        content="Health and nutrition body.",
        filename="raw.md",
        classification="PERSONAL",
    )
    assert "authored_by: claude" in note_content


def test_build_note_personal_includes_claude_callout_under_tldr():
    from datetime import date
    note_content, _ = ip.build_note(
        title="Mediterranean Diet",
        content="Health and nutrition body.",
        filename="raw.md",
        classification="PERSONAL",
    )
    # Callout sits between the TL;DR line and the first ## section
    tldr_idx = note_content.index("> **TL;DR:**")
    detail_idx = note_content.index("## Detail")
    callout_idx = note_content.index("> [!claude]")
    assert tldr_idx < callout_idx < detail_idx
    # Exact callout line — catches em-dash drift, missing period, wrong date format
    expected = f"> [!claude] Authored by Claude — ingested from perplexity, {date.today().isoformat()}."
    assert expected in note_content


def test_build_note_technical_omits_authorship_marker():
    note_content, _ = ip.build_note(
        title="Swift Concurrency",
        content="async await actors.",
        filename="raw.md",
        classification="TECHNICAL",
    )
    assert "authored_by: claude" not in note_content
    assert "> [!claude]" not in note_content

