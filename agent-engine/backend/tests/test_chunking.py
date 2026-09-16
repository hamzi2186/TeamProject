from app.services.chunking import MarkdownChunker


def test_markdown_chunker_header_hierarchy():
    text = """# Main Architecture

This is general architecture context.

## Subsystem Alpha

Alpha manages data crawling.

### Subsystem Alpha Details

Detailed alpha specifications.

## Subsystem Beta

Beta manages search indexing.
"""
    chunker = MarkdownChunker(max_chunk_chars=1000)
    chunks = chunker.chunk(text)

    assert len(chunks) == 4
    assert chunks[0].header_path == "Main Architecture"
    assert "general architecture context" in chunks[0].content

    assert chunks[1].header_path == "Main Architecture > Subsystem Alpha"
    assert "Alpha manages data crawling" in chunks[1].content

    assert chunks[2].header_path == "Main Architecture > Subsystem Alpha > Subsystem Alpha Details"
    assert "Detailed alpha specifications" in chunks[2].content

    assert chunks[3].header_path == "Main Architecture > Subsystem Beta"
    assert "Beta manages search indexing" in chunks[3].content


def test_markdown_chunker_determinism():
    text = """# Deterministic Test

Paragraph 1 is here.

## Section 2

Paragraph 2 is here.
"""
    chunker = MarkdownChunker()
    run1 = chunker.chunk(text)
    run2 = chunker.chunk(text)

    assert len(run1) == len(run2)
    for c1, c2 in zip(run1, run2, strict=False):
        assert c1.chunk_index == c2.chunk_index
        assert c1.header_path == c2.header_path
        assert c1.content == c2.content
        assert c1.content_hash == c2.content_hash


def test_markdown_chunker_large_paragraph_split():
    long_para = "A" * 800
    long_para_2 = "B" * 800
    text = f"# Section\n\n{long_para}\n\n{long_para_2}"

    chunker = MarkdownChunker(max_chunk_chars=1000)
    chunks = chunker.chunk(text)

    assert len(chunks) >= 2
    for c in chunks:
        assert c.header_path == "Section"
        assert len(c.content) <= 1200

