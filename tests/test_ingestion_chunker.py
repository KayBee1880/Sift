from pathlib import Path

from app.ingestion.chunker import (
    MIN_SECTION_TOKENS,
    SAFE_TOKEN_BUDGET,
    chunk_document,
    count_tokens,
)
from app.ingestion.parser import parse_markdown_document, parse_markdown_text

CORPUS_ROOT = Path(__file__).resolve().parent.parent / "corpus"

# A body long enough to individually clear MIN_SECTION_TOKENS on its own, so tests
# about non-merging behavior aren't accidentally affected by the merge-small-
# sections logic merging tiny fixture bodies together. Verified empirically
# (test_long_enough_body_actually_clears_the_merge_floor below), not just assumed
# from eyeballing the word count, after an earlier draft of this fixture turned out
# to be too short (52 tokens against an 80-token floor) and silently made several
# "non-merging" tests exercise merging behavior instead.
_LONG_ENOUGH_BODY = (
    "This section describes a realistic amount of content, long enough on its own "
    "to comfortably clear the minimum section token floor without needing to merge "
    "with any neighboring section, so tests using this body are specifically "
    "exercising non-merging behavior, not accidentally relying on it. Padded with "
    "additional realistic sentences here specifically to clear that floor with a "
    "comfortable margin, verified directly below rather than assumed. A few more "
    "sentences follow purely to add margin: this is padding text, added deliberately "
    "to push the total well past the minimum section token floor with room to spare, "
    "not just barely over it."
)  # 115 tokens, verified directly, comfortably clears MIN_SECTION_TOKENS (80)


def test_long_enough_body_actually_clears_the_merge_floor():
    # A guard against the fixture itself silently drifting under the floor again,
    # which would make every other test using it pass for the wrong reason.
    assert count_tokens(_LONG_ENOUGH_BODY) >= MIN_SECTION_TOKENS


def test_preamble_folded_into_first_section_only():
    text = (
        f"# Title\n\n**Severity:** SEV2\n\n## Summary\n\n{_LONG_ENOUGH_BODY}\n\n"
        f"## Impact\n\n{_LONG_ENOUGH_BODY}\n"
    )
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    assert chunks[0].section_anchor == "Summary"
    assert chunks[0].text.startswith("**Severity:** SEV2")
    assert _LONG_ENOUGH_BODY in chunks[0].text

    assert chunks[1].section_anchor == "Impact"
    assert "Severity" not in chunks[1].text


def test_raw_chunk_text_has_no_embedding_header_for_unmerged_section():
    text = f"# My Title\n\n## A Section\n\n{_LONG_ENOUGH_BODY}\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")
    assert chunks[0].text == _LONG_ENOUGH_BODY
    assert "My Title" not in chunks[0].text
    assert "A Section" not in chunks[0].text  # heading lives in section_anchor, not text, when unmerged


def test_embedding_text_includes_title_and_section_for_unmerged_section():
    text = f"# My Title\n\n## A Section\n\n{_LONG_ENOUGH_BODY}\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")
    assert chunks[0].embedding_text == f"My Title\n\nA Section\n\n{_LONG_ENOUGH_BODY}"


def test_section_index_is_deterministic_and_matches_document_order():
    text = (
        f"# Title\n\n## First\n\n{_LONG_ENOUGH_BODY}\n\n"
        f"## Second\n\n{_LONG_ENOUGH_BODY}\n\n"
        f"## Third\n\n{_LONG_ENOUGH_BODY}\n"
    )
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")
    assert [c.section_index for c in chunks] == [0, 1, 2]
    assert [c.section_anchor for c in chunks] == ["First", "Second", "Third"]


def test_section_chunk_index_is_zero_for_normal_sized_sections():
    text = f"# Title\n\n## Only Section\n\n{_LONG_ENOUGH_BODY}\n"
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
    text = f"# Title\n\n## Empty\n\n## Real\n\n{_LONG_ENOUGH_BODY}\n"
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


# --- Merge-small-sections behavior (adopted 2026-09-08, see decision log) ---


def test_small_adjacent_sections_merge_into_one_chunk():
    text = "# Title\n\n## Small One\n\na\n\n## Small Two\n\nb\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    assert len(chunks) == 1
    assert chunks[0].section_anchor == "Small One + Small Two"
    assert chunks[0].section_index == 0  # the first merged section's original index


def test_merged_chunk_text_interleaves_headings_with_their_own_body():
    text = "# Title\n\n## Small One\n\na\n\n## Small Two\n\nb\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    assert chunks[0].text == "Small One\n\na\n\nSmall Two\n\nb"
    assert chunks[0].embedding_text == "Title\n\nSmall One\n\na\n\nSmall Two\n\nb"


def test_large_section_does_not_merge_with_small_neighbor():
    # A small section between two large ones, not last in the document, so this
    # specifically exercises the forward-accumulation path, not the trailing-
    # section merge-backward fallback (see the next test for that path): "Large"
    # already clears the floor alone and closes its own group immediately, then
    # "Small" merges forward into "AlsoLarge" instead of backward into "Large".
    text = (
        f"# Title\n\n## Large\n\n{_LONG_ENOUGH_BODY}\n\n"
        f"## Small\n\ntiny\n\n## AlsoLarge\n\n{_LONG_ENOUGH_BODY}\n"
    )
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    assert [c.section_anchor for c in chunks] == ["Large", "Small + AlsoLarge"]


def test_trailing_small_section_merges_backward_into_previous_group():
    text = f"# Title\n\n## Large\n\n{_LONG_ENOUGH_BODY}\n\n## Trailing Small\n\ntiny\n"
    doc = parse_markdown_text(text)
    chunks = chunk_document(doc, "test-doc")

    # The trailing "Trailing Small" section never reaches MIN_SECTION_TOKENS on its
    # own and is the last section in the document, so it merges backward into the
    # previous group rather than standing alone as an under-sized final chunk.
    assert len(chunks) == 1
    assert chunks[0].section_anchor == "Large + Trailing Small"


def test_representative_incident_postmortem_chunking_from_frozen_corpus():
    path = CORPUS_ROOT / "incidents" / "payments-gateway-timeout-connection-pool.md"
    doc = parse_markdown_document(path)
    chunks = chunk_document(doc, "incidents/payments-gateway-timeout-connection-pool")

    # Merge-small-sections groups the postmortem's 7 original sections into 4
    # chunks (verified against the merge-small-sections experiment, decision log
    # 2026-09-08): Summary+Timeline, Impact+Root Cause, Evidence alone, and
    # Resolution+Follow-up Actions.
    assert len(chunks) == 4
    assert [c.section_anchor for c in chunks] == [
        "Summary + Timeline",
        "Impact + Root Cause",
        "Evidence",
        "Resolution + Follow-up Actions",
    ]
    assert chunks[0].text.startswith("Summary\n\n**Severity:** SEV2")
    assert all(c.section_chunk_index == 0 for c in chunks)
    assert all(count_tokens(c.embedding_text) <= SAFE_TOKEN_BUDGET for c in chunks)


def test_representative_runbook_chunking_from_frozen_corpus():
    path = CORPUS_ROOT / "runbooks" / "payments-gateway-timeout-troubleshooting.md"
    doc = parse_markdown_document(path)
    chunks = chunk_document(doc, "runbooks/payments-gateway-timeout-troubleshooting")

    assert len(chunks) == 3
    assert chunks[0].section_anchor == "Purpose + Symptoms"
    assert "Severity" not in chunks[0].text  # no preamble in this document type
