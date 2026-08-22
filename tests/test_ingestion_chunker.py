from pathlib import Path

from app.ingestion.chunker import SAFE_TOKEN_BUDGET, chunk_document, count_tokens
from app.ingestion.parser import parse_markdown_document, parse_markdown_text

CORPUS_ROOT = Path(__file__).resolve().parent.parent / "corpus"


def test_preamble_folded_into_first_section_only():
    text = "# Title\n\n**Severity:** SEV2\n\n## Summary\n\nsomething happened\n\n## Impact\n\nimpact text\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    assert chunks[0].section_anchor == "Summary"
    assert chunks[0].text.startswith("**Severity:** SEV2")
    assert "something happened" in chunks[0].text

    assert chunks[1].section_anchor == "Impact"
    assert "Severity" not in chunks[1].text


def test_raw_chunk_text_has_no_embedding_header():
    text = "# My Title\n\n## A Section\n\nplain body content\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")
    assert chunks[0].text == "plain body content"
    assert "My Title" not in chunks[0].text
    assert "Section:" not in chunks[0].text


def test_embedding_text_includes_title_and_section_prefix():
    text = "# My Title\n\n## A Section\n\nplain body content\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")
    assert chunks[0].embedding_text == "My Title\nSection: A Section\n\nplain body content"


def test_section_index_is_deterministic_and_matches_document_order():
    text = "# Title\n\n## First\n\na\n\n## Second\n\nb\n\n## Third\n\nc\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")
    assert [c.section_index for c in chunks] == [0, 1, 2]
    assert [c.section_anchor for c in chunks] == ["First", "Second", "Third"]


def test_section_chunk_index_is_zero_for_normal_sized_sections():
    text = "# Title\n\n## Only Section\n\nshort body\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")
    assert len(chunks) == 1
    assert chunks[0].section_chunk_index == 0


def test_oversized_section_triggers_deterministic_subsplit():
    paragraph = "This is a padding sentence with a handful of extra words in it. " * 3
    long_body = "\n\n".join(paragraph for _ in range(40))
    text = f"# Title\n\n## Huge Section\n\n{long_body}\n"
    doc = parse_markdown_text(text)

    assert count_tokens(long_body) > SAFE_TOKEN_BUDGET

    chunks = chunk_document(doc, "test-doc")
    assert len(chunks) > 1


def test_subchunks_from_oversized_section_share_same_section_anchor_and_index():
    paragraph = "This is a padding sentence with a handful of extra words in it. " * 3
    long_body = "\n\n".join(paragraph for _ in range(40))
    text = f"# Title\n\n## Huge Section\n\n{long_body}\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    assert len(chunks) > 1
    assert all(c.section_anchor == "Huge Section" for c in chunks)
    assert all(c.section_index == 0 for c in chunks)
    assert [c.section_chunk_index for c in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert count_tokens(chunk.embedding_text) <= SAFE_TOKEN_BUDGET + 20  # small slack for header overlap


def test_empty_section_produces_no_chunk():
    text = "# Title\n\n## Empty\n\n## Real\n\nactual content\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")
    assert [c.section_anchor for c in chunks] == ["Real"]


def test_document_with_no_sections_but_preamble_becomes_one_chunk():
    text = "# Title\n\nJust prose, no headings.\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")
    assert len(chunks) == 1
    assert chunks[0].section_anchor is None
    assert chunks[0].section_index == 0
    assert chunks[0].text == "Just prose, no headings."


def test_document_with_no_sections_and_no_preamble_produces_no_chunks():
    text = "# Title\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")
    assert chunks == []


def test_representative_incident_postmortem_chunking_from_frozen_corpus():
    path = CORPUS_ROOT / "incidents" / "payments-gateway-timeout-connection-pool.md"
    doc = parse_markdown_document(path)
    chunks = chunk_document(doc, "incidents/payments-gateway-timeout-connection-pool")

    assert len(chunks) == 7  # one per H2 section, no sub-splitting expected
    assert chunks[0].section_anchor == "Summary"
    assert chunks[0].text.startswith("**Severity:** SEV2")
    assert all(c.section_chunk_index == 0 for c in chunks)
    assert all(count_tokens(c.embedding_text) <= SAFE_TOKEN_BUDGET for c in chunks)


def test_representative_runbook_chunking_from_frozen_corpus():
    path = CORPUS_ROOT / "runbooks" / "payments-gateway-timeout-troubleshooting.md"
    doc = parse_markdown_document(path)
    chunks = chunk_document(doc, "runbooks/payments-gateway-timeout-troubleshooting")

    assert len(chunks) == 6
    assert chunks[0].section_anchor == "Purpose"
    assert "Severity" not in chunks[0].text  # no preamble in this document type
