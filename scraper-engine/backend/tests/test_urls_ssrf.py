import pytest

from app.services.ssrf import UnsafeTargetError, validate_public_url
from app.services.urls import canonicalize_crawl_url, normalize_website_url


@pytest.mark.parametrize(
    ("value", "expected_url", "expected_key"),
    [
        ("example.com", "https://example.com/", "example.com"),
        ("HTTP://WWW.Example.COM:80/", "https://example.com/", "example.com"),
        ("https://example.com/path/#section", "https://example.com/path", "example.com/path"),
        (
            "https://example.com/?utm_source=test&b=2&a=1",
            "https://example.com/",
            "example.com",
        ),
    ],
)
def test_website_normalization(value, expected_url, expected_key):
    normalized = normalize_website_url(value)
    assert normalized.normalized_url == expected_url
    assert normalized.normalized_key == expected_key


def test_crawl_url_relative_tracking_and_unsupported_links():
    assert canonicalize_crawl_url("/about/?utm_source=x", base_url="https://Example.com") == (
        "https://example.com/about"
    )
    assert canonicalize_crawl_url("mailto:test@example.com") is None
    assert canonicalize_crawl_url("file:///etc/passwd") is None
    assert canonicalize_crawl_url("/document.pdf", base_url="https://example.com") is None
    assert canonicalize_crawl_url("https://www.example.com/") == "https://www.example.com/"


def test_important_business_pages_are_eligible():
    base = "https://example.com"
    eligible_urls = [
        ("/", "https://example.com/"),
        ("/about", "https://example.com/about"),
        ("/about-us/", "https://example.com/about-us"),
        ("/services", "https://example.com/services"),
        ("/services/individual-therapy/", "https://example.com/services/individual-therapy"),
        ("/products/suite", "https://example.com/products/suite"),
        ("/pricing", "https://example.com/pricing"),
        ("/faq", "https://example.com/faq"),
        ("/contact", "https://example.com/contact"),
        ("/contact-us/", "https://example.com/contact-us"),
        ("/locations/downtown", "https://example.com/locations/downtown"),
        ("/team", "https://example.com/team"),
        ("/our-team/dr-smith", "https://example.com/our-team/dr-smith"),
        ("/staff", "https://example.com/staff"),
        ("/modalities-in-therapy", "https://example.com/modalities-in-therapy"),
        ("/administrative-services", "https://example.com/administrative-services"),
        ("/feed-your-mind", "https://example.com/feed-your-mind"),
    ]
    for rel, expected in eligible_urls:
        assert canonicalize_crawl_url(rel, base_url=base) == expected, f"Failed for {rel}"


def test_excluded_url_classes_are_rejected():
    base = "https://example.com"
    excluded_urls = [
        # Admin / Auth
        "/wp-admin",
        "/wp-admin/",
        "/wp-admin/post.php",
        "/wp-login.php",
        "/admin",
        "/admin/settings",
        "/login",
        "/signin",
        "/sign-in",
        "/signup",
        "/sign-up",
        "/register",
        "/cart",
        "/checkout",
        "/xmlrpc.php",
        "/wp-json",
        # Feeds
        "/feed",
        "/feed/",
        "/blog/feed/",
        "/rss.xml",
        "/atom.xml",
        "/?feed=rss2",
        # Search results
        "/?s=therapy",
        "/search",
        "/search?q=dr",
        "/?query=test",
        # Assets & binary downloads
        "/logo.png",
        "/photo.jpg",
        "/banner.webp",
        "/document.pdf",
        "/spreadsheet.xlsx",
        "/styles.css",
        "/script.js",
        "/archive.zip",
        "/installer.exe",
        "/video.mp4",
        # Unsupported schemes
        "mailto:info@example.com",
        "tel:+1234567890",
        "javascript:void(0)",
    ]
    for url in excluded_urls:
        assert canonicalize_crawl_url(url, base_url=base) is None, f"Should be excluded: {url}"


def test_canonical_deduplication_and_tracking_stripping():
    base = "https://example.com"
    assert (
        canonicalize_crawl_url("/services/", base_url=base)
        == canonicalize_crawl_url("/services", base_url=base)
        == "https://example.com/services"
    )
    assert (
        canonicalize_crawl_url(
            "/faq/?utm_source=google&utm_medium=cpc&fbclid=xyz&gclid=123",
            base_url=base,
        )
        == "https://example.com/faq"
    )
    assert (
        canonicalize_crawl_url("/page?b=2&a=1&utm_term=test", base_url=base)
        == "https://example.com/page?a=1&b=2"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]",
        "http://[fc00::1]",
        "file:///etc/passwd",
    ],
)
async def test_direct_ssrf_targets_are_rejected(url):
    with pytest.raises(UnsafeTargetError):
        await validate_public_url(url)


@pytest.mark.asyncio
async def test_hostname_resolving_private_is_rejected():
    async def resolver(_host, _port):
        return ["192.168.1.8"]

    with pytest.raises(UnsafeTargetError):
        await validate_public_url("https://public-looking.example", resolver=resolver)


@pytest.mark.asyncio
async def test_public_resolution_is_allowed():
    async def resolver(_host, _port):
        return ["93.184.216.34"]

    assert await validate_public_url("https://example.com", resolver=resolver) == ["93.184.216.34"]
