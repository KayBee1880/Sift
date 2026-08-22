import re
from dataclasses import dataclass, field
from pathlib import Path

_H1_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_H2_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)


@dataclass
class ParsedSection:
    index: int
    heading: str
    body: str


@dataclass
class ParsedDocument:
    title: str
    preamble: str
    sections: list[ParsedSection] = field(default_factory=list)
    source_path: Path | None = None


def parse_markdown_document(path: Path) -> ParsedDocument:
    text = path.read_text(encoding="utf-8")
    return parse_markdown_text(text, source_path=path)


def parse_markdown_text(text: str, source_path: Path | None = None) -> ParsedDocument:
    h1_match = _H1_PATTERN.search(text)
    if not h1_match:
        raise ValueError(f"{source_path or '<string>'}: no H1 title found")
    title = h1_match.group(1).strip()

    after_title = text[h1_match.end():]
    h2_matches = list(_H2_PATTERN.finditer(after_title))

    if not h2_matches:
        preamble = after_title.strip()
        return ParsedDocument(title=title, preamble=preamble, sections=[], source_path=source_path)

    preamble = after_title[: h2_matches[0].start()].strip()

    sections = []
    for i, match in enumerate(h2_matches):
        heading = match.group(1).strip()
        body_start = match.end()
        body_end = h2_matches[i + 1].start() if i + 1 < len(h2_matches) else len(after_title)
        body = after_title[body_start:body_end].strip()
        sections.append(ParsedSection(index=i, heading=heading, body=body))

    return ParsedDocument(title=title, preamble=preamble, sections=sections, source_path=source_path)
