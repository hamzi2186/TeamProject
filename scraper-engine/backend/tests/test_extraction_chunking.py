from app.services.chunking import DeterministicChunker
from app.services.extraction import extract_page


def test_extraction_removes_noise_and_preserves_metadata_and_links():
    page = extract_page(
        """
        <html><head><title> Example Company </title>
        <meta name="description" content="Practical care services">
        <link rel="canonical" href="/about"></head>
        <body><nav>Repeated navigation</nav><main><h1>Care that helps</h1>
        <p>Our clinicians provide useful and meaningful services for families.</p></main>
        <script>secretNoise()</script><style>.hidden{display:none}</style>
        <a href="/contact?utm_source=test">Contact</a></body></html>
        """,
        url="https://example.com/about?ref=tracking",
    )
    assert page.title == "Example Company"
    assert page.meta_description == "Practical care services"
    assert page.canonical_url == "https://example.com/about"
    assert "secretNoise" not in page.text
    assert "Care that helps" in page.text
    assert page.links == ["https://example.com/contact"]


def test_empty_page_and_deterministic_chunking():
    empty = extract_page("<html><script>only()</script></html>", url="https://example.com")
    assert empty.text == ""
    text = "\n\n".join(f"Section {index} " + "useful words " * 30 for index in range(12))
    chunker = DeterministicChunker(max_tokens=100, overlap_tokens=15)
    first = chunker.chunk(text)
    second = chunker.chunk(text)
    assert first == second
    assert len(first) > 1
    assert [chunk.index for chunk in first] == list(range(len(first)))
    assert all(chunk.content.strip() and chunk.token_count <= 100 for chunk in first)
