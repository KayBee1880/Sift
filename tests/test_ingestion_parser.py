from pathlib import Path

import pytest

from app.ingestion.parser import parse_markdown_document, parse_markdown_text

CORPUS_ROOT = Path(__file__).resolve().parent.parent / "corpus"


def test_title_extraction():
    doc = parse_markdown_text("# My Document Title\n\n## First Section\n\nBody text.\n")
    assert doc.title == "My Document Title"


def test_h2_section_extraction_and_ordering():
    text = """# Title

## Alpha

alpha body

## Beta

beta body

## Gamma

gamma body
"""
    doc = parse_markdown_text(text)
    assert [s.heading for s in doc.sections] == ["Alpha", "Beta", "Gamma"]
    assert [s.index for s in doc.sections] == [0, 1, 2]
    assert doc.sections[1].body == "beta body"


def test_section_anchors_preserve_exact_heading_text():
    text = "# Title\n\n## Root Cause\n\nsomething happened\n"
    doc = parse_markdown_text(text)
    assert doc.sections[0].heading == "Root Cause"


def test_preamble_detected_when_present():
    text = "# Title\n\n**Severity:** SEV2\n\n## Summary\n\nbody\n"
    doc = parse_markdown_text(text)
    assert doc.preamble == "**Severity:** SEV2"
    assert doc.sections[0].heading == "Summary"


def test_preamble_empty_when_absent():
    text = "# Title\n\n## Summary\n\nbody\n"
    doc = parse_markdown_text(text)
    assert doc.preamble == ""


def test_document_with_no_h2_sections_treats_all_content_as_preamble():
    text = "# Title\n\nJust some prose, no sections at all.\n"
    doc = parse_markdown_text(text)
    assert doc.sections == []
    assert doc.preamble == "Just some prose, no sections at all."


def test_missing_h1_raises():
    with pytest.raises(ValueError, match="no H1 title found"):
        parse_markdown_text("## Just a section\n\nbody\n")


def test_empty_section_body_is_preserved_as_empty_string():
    text = "# Title\n\n## Empty\n\n## Next\n\nreal body\n"
    doc = parse_markdown_text(text)
    assert doc.sections[0].heading == "Empty"
    assert doc.sections[0].body == ""
    assert doc.sections[1].body == "real body"


def test_representative_incident_postmortem_from_frozen_corpus():
    path = CORPUS_ROOT / "incidents" / "payments-gateway-timeout-connection-pool.md"
    doc = parse_markdown_document(path)
    assert doc.title == "INC-2024-0512: Payments API Gateway Timeout"
    assert doc.preamble == "**Severity:** SEV2"
    headings = [s.heading for s in doc.sections]
    assert headings == [
        "Summary",
        "Timeline",
        "Impact",
        "Root Cause",
        "Evidence",
        "Resolution",
        "Follow-up Actions",
    ]


def test_representative_runbook_with_different_structure_from_frozen_corpus():
    path = CORPUS_ROOT / "runbooks" / "payments-gateway-timeout-troubleshooting.md"
    doc = parse_markdown_document(path)
    assert doc.title == "Gateway Timeout Troubleshooting"
    assert doc.preamble == ""
    headings = [s.heading for s in doc.sections]
    assert headings == [
        "Purpose",
        "Symptoms",
        "Diagnostic Steps",
        "Common Causes",
        "Resolution Steps",
        "Escalation",
    ]
