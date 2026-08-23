import logging
import sys
from pathlib import Path

from app.db.session import SessionLocal
from app.ingestion.pipeline import ingest_document

logger = logging.getLogger(__name__)


def ingest_corpus(corpus_root: Path) -> dict[str, int]:
    """Ingest every corpus markdown document under corpus_root.

    Each document is committed independently by ingest_document, so a failure
    partway through leaves already-processed documents persisted rather than
    rolling back the whole run.
    """
    counts = {"created": 0, "updated": 0, "skipped": 0}
    session = SessionLocal()
    try:
        files = sorted(p for p in corpus_root.rglob("*.md") if p.name != "MANIFEST.md")
        for path in files:
            result = ingest_document(path, corpus_root, session)
            counts[result.status] += 1
    finally:
        session.close()
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    corpus_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("corpus")
    counts = ingest_corpus(corpus_root)
    print(f"created={counts['created']} updated={counts['updated']} skipped={counts['skipped']}")
