import re
import urllib.robotparser
import xml.etree.ElementTree as ET
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.services.extraction import ExtractedPage, extract_page
from app.services.renderer import RenderingError, render_page
from app.services.ssrf import validate_public_url
from app.services.urls import URLValidationError, canonicalize_crawl_url, normalized_host

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
HTML_TYPES = {"text/html", "application/xhtml+xml"}
XML_TYPES = {"application/xml", "text/xml", "application/rss+xml"}


class CrawlError(RuntimeError):
    retryable = False


class RetryableCrawlError(CrawlError):
    retryable = True


@dataclass(frozen=True)
class FetchedResource:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    text: str


@dataclass(frozen=True)
class CrawledPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    depth: int
    fetched_at: datetime
    extracted: ExtractedPage


@dataclass
class CrawlResult:
    pages: list[CrawledPage] = field(default_factory=list)
    discovered_count: int = 0
    errors: list[str] = field(default_factory=list)
    partial_reason: str | None = None


class SafeHTTPFetcher:
    def __init__(
        self,
        *,
        timeout_seconds: float,
        user_agent: str,
        max_redirects: int,
        validator: Callable[[str], Awaitable[list[str]]] = validate_public_url,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._validator = validator
        self._max_redirects = max_redirects
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8",
            },
        )

    async def fetch(self, url: str) -> FetchedResource:
        current = url
        visited: set[str] = set()
        for _ in range(self._max_redirects + 1):
            if current in visited:
                raise CrawlError("Redirect loop detected")
            visited.add(current)
            await self._validator(current)
            try:
                async with self._client.stream("GET", current) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise CrawlError("Redirect response did not include a destination")
                        destination = urljoin(current, location)
                        parsed_dest = urlsplit(destination)
                        if parsed_dest.scheme.casefold() not in {"http", "https"}:
                            raise CrawlError("Redirect destination is unsupported")
                        await self._validator(destination)
                        current = destination
                        continue
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_RESPONSE_BYTES:
                            raise CrawlError("Response exceeded the crawler size limit")
                    media_type = (
                        response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    )
                    encoding = response.encoding or "utf-8"
                    text = bytes(content).decode(encoding, errors="replace")
                    return FetchedResource(
                        requested_url=url,
                        final_url=str(response.url),
                        status_code=response.status_code,
                        content_type=media_type,
                        text=text,
                    )
            except httpx.TimeoutException as exc:
                raise RetryableCrawlError("Website request timed out") from exc
            except httpx.NetworkError as exc:
                raise RetryableCrawlError("Website request failed") from exc
        raise CrawlError("Website exceeded the redirect limit")

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class WebsiteCrawler:
    def __init__(
        self,
        *,
        fetcher: SafeHTTPFetcher,
        max_pages: int,
        max_depth: int,
        minimum_text_characters: int,
        enable_playwright_fallback: bool,
        renderer: Callable[..., Awaitable[str]] = render_page,
        validator: Callable[[str], Awaitable[list[str]]] = validate_public_url,
    ) -> None:
        self._fetcher = fetcher
        self._max_pages = max_pages
        self._max_depth = max_depth
        self._minimum_text = minimum_text_characters
        self._playwright = enable_playwright_fallback
        self._renderer = renderer
        self._validator = validator

    async def crawl(self, seed_url: str) -> CrawlResult:
        await self._validator(seed_url)
        origin_host = normalized_host(seed_url)
        parsed_seed = urlsplit(seed_url)
        origin = urlunsplit((parsed_seed.scheme, parsed_seed.netloc, "", "", ""))
        robots = urllib.robotparser.RobotFileParser()
        robots.set_url(f"{origin}/robots.txt")
        sitemap_urls = [f"{origin}/sitemap.xml"]
        errors: list[str] = []
        try:
            robots_resource = await self._fetcher.fetch(f"{origin}/robots.txt")
            if robots_resource.status_code < 400:
                robots.parse(robots_resource.text.splitlines())
                sitemap_urls = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots_resource.text)
                sitemap_urls.append(f"{origin}/sitemap.xml")
            else:
                robots.parse([])
        except (CrawlError, URLValidationError) as exc:
            robots.parse([])
            errors.append(f"robots.txt: {exc}")

        discovered: list[str] = [seed_url]
        discovered.extend(await self._discover_sitemaps(sitemap_urls, origin_host, errors))
        queue: deque[tuple[str, int]] = deque()
        queued: set[str] = set()
        for url in discovered:
            canonical = canonicalize_crawl_url(url)
            if canonical and canonical not in queued:
                queued.add(canonical)
                queue.append((canonical, 0 if canonical == seed_url else 1))

        result = CrawlResult(errors=errors)
        visited: set[str] = set()
        content_hashes: set[str] = set()
        retryable_failures = 0
        while queue:
            if self._max_pages and len(visited) >= self._max_pages:
                result.partial_reason = f"Crawl page limit of {self._max_pages} reached"
                break
            url, depth = queue.popleft()
            if url in visited or depth > self._max_depth:
                continue
            visited.add(url)
            if normalized_host(url) != origin_host:
                continue
            if not robots.can_fetch("*", url):
                continue
            try:
                resource = await self._fetcher.fetch(url)
            except (CrawlError, URLValidationError) as exc:
                if getattr(exc, "retryable", False):
                    retryable_failures += 1
                result.errors.append(f"{url}: {exc}")
                continue
            if normalized_host(resource.final_url) != origin_host:
                result.errors.append(f"{url}: redirect left the allowed site")
                continue
            if resource.status_code >= 400:
                result.errors.append(f"{url}: HTTP {resource.status_code}")
                continue
            if resource.content_type not in HTML_TYPES:
                result.errors.append(f"{url}: unsupported content type")
                continue
            extracted = extract_page(resource.text, url=resource.final_url)
            if len(extracted.text) < self._minimum_text and self._playwright:
                try:
                    rendered = await self._renderer(
                        resource.final_url,
                        validator=self._validator,
                    )
                    extracted = extract_page(rendered, url=resource.final_url)
                except RenderingError as exc:
                    result.errors.append(f"{url}: {exc}")
            if normalized_host(extracted.canonical_url) != origin_host:
                extracted = replace(extracted, canonical_url=resource.final_url)
            for link in extracted.links:
                if (
                    depth < self._max_depth
                    and normalized_host(link) == origin_host
                    and link not in queued
                ):
                    queued.add(link)
                    queue.append((link, depth + 1))
            if len(extracted.text) < self._minimum_text:
                result.errors.append(f"{url}: no meaningful content")
                continue
            if extracted.content_hash in content_hashes:
                continue
            content_hashes.add(extracted.content_hash)
            result.pages.append(
                CrawledPage(
                    requested_url=url,
                    final_url=resource.final_url,
                    status_code=resource.status_code,
                    content_type=resource.content_type,
                    depth=depth,
                    fetched_at=datetime.now(UTC),
                    extracted=extracted,
                )
            )
        result.discovered_count = len(queued)
        if not result.pages:
            if retryable_failures:
                raise RetryableCrawlError("Website was temporarily unavailable")
            raise CrawlError("No meaningful website content could be extracted")
        return result

    async def _discover_sitemaps(
        self, sitemap_urls: list[str], origin_host: str, errors: list[str]
    ) -> list[str]:
        pages: list[str] = []
        pending = deque(dict.fromkeys(sitemap_urls))
        visited: set[str] = set()
        discovery_limit = self._max_pages * 5 if self._max_pages else 50_000
        while pending and len(visited) < 20:
            sitemap_url = pending.popleft()
            canonical = canonicalize_crawl_url(sitemap_url, allow_sitemap=True)
            if not canonical or canonical in visited or normalized_host(canonical) != origin_host:
                continue
            visited.add(canonical)
            try:
                resource = await self._fetcher.fetch(canonical)
                if resource.status_code >= 400:
                    continue
                root = ET.fromstring(resource.text)
            except (CrawlError, URLValidationError, ET.ParseError) as exc:
                errors.append(f"{canonical}: invalid sitemap ({exc})")
                continue
            root_name = root.tag.rsplit("}", 1)[-1].casefold()
            locations = [
                (element.text or "").strip()
                for element in root.iter()
                if element.tag.rsplit("}", 1)[-1].casefold() == "loc" and element.text
            ]
            if root_name == "sitemapindex":
                pending.extend(locations)
            else:
                pages.extend(locations[: max(0, discovery_limit - len(pages))])
            if len(pages) >= discovery_limit:
                break
        return pages
