import httpx
import pytest

from app.services.crawler import SafeHTTPFetcher, WebsiteCrawler
from app.services.ssrf import UnsafeTargetError, validate_public_url


async def public_validator(url: str):
    async def resolver(_host, _port):
        return ["93.184.216.34"]

    return await validate_public_url(url, resolver=resolver)


@pytest.mark.asyncio
async def test_crawler_discovers_sitemap_relative_links_and_prevents_loops():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml"
            )
        if path == "/sitemap.xml":
            return httpx.Response(
                200,
                headers={"content-type": "application/xml"},
                text="<urlset><url><loc>https://example.com/about</loc></url></urlset>",
            )
        if path == "/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<main><h1>Home</h1><p>"
                + "Welcome content " * 20
                + "</p></main><a href='/about'>About</a><a href='https://other.example/out'>External</a>",
            )
        if path == "/about":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<main><h1>About</h1><p>"
                + "Different company story " * 20
                + "</p></main><a href='/'>Home</a>",
            )
        return httpx.Response(404, headers={"content-type": "text/html"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = SafeHTTPFetcher(
        timeout_seconds=2,
        user_agent="test",
        max_redirects=3,
        validator=public_validator,
        client=client,
    )
    crawler = WebsiteCrawler(
        fetcher=fetcher,
        max_pages=10,
        max_depth=3,
        minimum_text_characters=20,
        enable_playwright_fallback=False,
        validator=public_validator,
    )
    result = await crawler.crawl("https://example.com/")
    assert {page.final_url for page in result.pages} == {
        "https://example.com/",
        "https://example.com/about",
    }
    assert result.discovered_count == 2
    assert result.partial_reason is None


@pytest.mark.asyncio
async def test_redirect_to_private_target_is_rejected():
    def handler(_request):
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    fetcher = SafeHTTPFetcher(
        timeout_seconds=2,
        user_agent="test",
        max_redirects=3,
        validator=public_validator,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(UnsafeTargetError):
        await fetcher.fetch("https://example.com/")


@pytest.mark.asyncio
async def test_page_limit_marks_partial_and_http_failures_do_not_abort_useful_crawl():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in {"/robots.txt", "/sitemap.xml"}:
            return httpx.Response(404, headers={"content-type": "text/plain"})
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<main><p>" + "Useful content " * 20 + "</p></main><a href='/two'>Two</a>",
        )

    fetcher = SafeHTTPFetcher(
        timeout_seconds=2,
        user_agent="test",
        max_redirects=3,
        validator=public_validator,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = await WebsiteCrawler(
        fetcher=fetcher,
        max_pages=1,
        max_depth=3,
        minimum_text_characters=20,
        enable_playwright_fallback=False,
        validator=public_validator,
    ).crawl("https://example.com/")
    assert len(result.pages) == 1
    assert result.partial_reason == "Crawl page limit of 1 reached"


def test_crawler_default_and_configured_limit():
    from app.core.config import Settings

    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/db",
        tpi_internal_service_token="test",
        scraper_internal_service_token="test",
    )
    assert settings.crawl_max_pages == 100

    custom = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/db",
        tpi_internal_service_token="test",
        scraper_internal_service_token="test",
        crawl_max_pages=50,
    )
    assert custom.crawl_max_pages == 50


@pytest.mark.asyncio
async def test_crawler_prioritizes_core_business_pages_over_pagination():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(
                200, text="User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml"
            )
        if path == "/sitemap.xml":
            return httpx.Response(
                200,
                headers={"content-type": "application/xml"},
                text="""<urlset>
                    <url><loc>https://example.com/pricing</loc></url>
                    <url><loc>https://example.com/team</loc></url>
                </urlset>""",
            )
        if path == "/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="""
                <html>
                <header>
                    <nav>
                        <a href="/about">About Us</a>
                        <a href="/services">Our Services</a>
                    </nav>
                </header>
                <main>
                    <h1>Welcome</h1>
                    <p>"""
                + "Important clinic content " * 15
                + """</p>
                    <a href="/category/news/page/2">Old News Page 2</a>
                    <a href="/wp-admin">Admin Dashboard</a>
                    <a href="/search?s=test">Search Results</a>
                    <a href="/flyer.pdf">Flyer Download</a>
                </main>
                <footer>
                    <a href="/contact">Contact Us</a>
                    <a href="/faq">FAQ</a>
                </footer>
                </html>
                """,
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=f"<main><h1>{path}</h1><p>Unique details about {path}. "
            + "Valuable page content " * 15
            + "</p></main>",
        )

    fetcher = SafeHTTPFetcher(
        timeout_seconds=2,
        user_agent="test",
        max_redirects=3,
        validator=public_validator,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    crawler = WebsiteCrawler(
        fetcher=fetcher,
        max_pages=5,
        max_depth=3,
        minimum_text_characters=20,
        enable_playwright_fallback=False,
        validator=public_validator,
    )
    result = await crawler.crawl("https://example.com/")
    assert len(result.pages) == 5
    crawled_urls = {page.final_url for page in result.pages}

    assert "https://example.com/" in crawled_urls
    assert "https://example.com/category/news/page/2" not in crawled_urls
    assert "https://example.com/wp-admin" not in crawled_urls
    assert "https://example.com/search" not in crawled_urls
    assert "https://example.com/flyer.pdf" not in crawled_urls
    assert result.partial_reason == "Crawl page limit of 5 reached"
