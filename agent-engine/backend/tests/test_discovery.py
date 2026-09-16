import hashlib
from pathlib import Path

from app.services.discovery import DocumentDiscoveryService


def test_discovery_and_title_extraction(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    # Module 1: scraper
    scraper_dir = docs_dir / "scraper"
    scraper_dir.mkdir()

    (scraper_dir / "overview.md").write_text(
        "# Scraper Engine Overview\n\nThis is an overview of the scraper engine.",
        encoding="utf-8",
    )
    (scraper_dir / "frontmatter.md").write_text(
        "---\ntitle: Custom Frontmatter Title\n---\n# Ignored Header\n\nBody text.",
        encoding="utf-8",
    )
    (scraper_dir / "no_header.md").write_text(
        "Just some plain text without any markdown header.",
        encoding="utf-8",
    )

    # Module 2: calling
    calling_dir = docs_dir / "calling"
    calling_dir.mkdir()
    (calling_dir / "setup.md").write_text(
        "# Calling Setup Guide\n\nCalling setup instructions.",
        encoding="utf-8",
    )

    service = DocumentDiscoveryService(docs_dir)

    # Discover all
    all_docs = service.discover()
    assert len(all_docs) == 4

    doc_map = {d.source_path: d for d in all_docs}
    assert "scraper/overview.md" in doc_map
    assert doc_map["scraper/overview.md"].title == "Scraper Engine Overview"
    assert doc_map["scraper/overview.md"].module_key == "scraper"
    assert doc_map["scraper/overview.md"].content_hash == hashlib.sha256(
        b"# Scraper Engine Overview\n\nThis is an overview of the scraper engine."
    ).hexdigest()

    assert doc_map["scraper/frontmatter.md"].title == "Custom Frontmatter Title"
    assert doc_map["scraper/no_header.md"].title == "No Header"

    # Filter by module
    scraper_only = service.discover(module_filter="scraper")
    assert len(scraper_only) == 3
    assert all(d.module_key == "scraper" for d in scraper_only)

    calling_only = service.discover(module_filter="calling")
    assert len(calling_only) == 1
    assert calling_only[0].module_key == "calling"
    assert calling_only[0].title == "Calling Setup Guide"


def test_discovery_ignores_hidden_and_non_md(tmp_path: Path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    scraper_dir = docs_dir / "scraper"
    scraper_dir.mkdir()
    (scraper_dir / "valid.md").write_text("# Valid\n\nContent", encoding="utf-8")
    (scraper_dir / ".hidden.md").write_text("# Hidden\n\nContent", encoding="utf-8")
    (scraper_dir / "notes.txt").write_text("Text file", encoding="utf-8")

    hidden_dir = docs_dir / ".git"
    hidden_dir.mkdir()
    (hidden_dir / "git_doc.md").write_text("# Git Doc\n\nContent", encoding="utf-8")

    service = DocumentDiscoveryService(docs_dir)
    docs = service.discover()
    assert len(docs) == 1
    assert docs[0].source_path == "scraper/valid.md"

