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
