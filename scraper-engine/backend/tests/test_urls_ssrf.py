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
