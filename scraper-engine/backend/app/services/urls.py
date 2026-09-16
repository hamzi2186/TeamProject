import ipaddress
import posixpath
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

TRACKING_PARAMETERS = {
    "_ga",
    "_gl",
    "fbclid",
    "gclid",
    "hscid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ref",
    "referrer",
    "source",
    "trk",
    "twclid",
    "yclid",
}
SEARCH_QUERY_PARAMETERS = {
    "keyword",
    "q",
    "query",
    "s",
    "search",
    "search_term",
}
SKIPPED_SCHEMES = {"mailto", "tel", "javascript", "data", "file", "ftp"}
SKIPPED_PATH_SEGMENTS = {
    "account",
    "admin",
    "atom",
    "cart",
    "checkout",
    "feed",
    "login",
    "logout",
    "my-account",
    "register",
    "rss",
    "search",
    "sign-in",
    "sign-out",
    "sign-up",
    "signin",
    "signout",
    "signup",
    "wp-admin",
    "wp-includes",
    "wp-json",
    "xmlrpc.php",
}
SKIPPED_PATH_PARTS = SKIPPED_PATH_SEGMENTS
SKIPPED_EXTENSIONS = {
    ".7z",
    ".ai",
    ".avi",
    ".bin",
    ".bmp",
    ".css",
    ".csv",
    ".dmg",
    ".doc",
    ".docx",
    ".eot",
    ".eps",
    ".exe",
    ".flv",
    ".gif",
    ".gz",
    ".ico",
    ".iso",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".m4a",
    ".m4v",
    ".map",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".ogv",
    ".otf",
    ".pdf",
    ".png",
    ".psd",
    ".rar",
    ".rtf",
    ".svg",
    ".tar",
    ".tgz",
    ".tif",
    ".tiff",
    ".ttf",
    ".wav",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
}


class URLValidationError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedWebsite:
    normalized_url: str
    normalized_key: str
    normalized_host: str


def _host(value: str) -> str:
    try:
        encoded = value.rstrip(".").encode("idna").decode("ascii").casefold()
    except UnicodeError as exc:
        raise URLValidationError("Website hostname is invalid") from exc
    return encoded[4:] if encoded.startswith("www.") else encoded


def _network_host(value: str) -> str:
    """Normalize a host without changing the address used for HTTP requests."""
    try:
        return value.rstrip(".").encode("idna").decode("ascii").casefold()
    except UnicodeError as exc:
        raise URLValidationError("Website hostname is invalid") from exc


def _port(parsed) -> int | None:
    try:
        return parsed.port
    except ValueError as exc:
        raise URLValidationError("Website port is invalid") from exc


def _path(value: str) -> str:
    if not value or value == "/":
        return ""
    normalized = posixpath.normpath(value)
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return quote(normalized, safe="/%:@!$&'()*+,;=-._~").rstrip("/")


def _query(value: str) -> str:
    pairs = []
    for key, item in parse_qsl(value, keep_blank_values=False):
        folded = key.casefold()
        if folded.startswith("utm_") or folded in TRACKING_PARAMETERS:
            continue
        pairs.append((key, item))
    return urlencode(sorted(pairs))


def normalize_website_url(value: str) -> NormalizedWebsite:
    raw = value.strip()
    if not raw:
        raise URLValidationError("Website URL is required")
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise URLValidationError("Only HTTP and HTTPS websites are supported")
    if parsed.username or parsed.password:
        raise URLValidationError("Website URLs must not contain credentials")
    if not parsed.hostname:
        raise URLValidationError("Website URL must contain a hostname")
    host = _host(parsed.hostname)
    port = _port(parsed)
    if port in {80, 443}:
        port = None
    try:
        address = ipaddress.ip_address(host)
        display_host = f"[{host}]" if address.version == 6 else host
    except ValueError:
        display_host = host
    authority = f"{display_host}:{port}" if port else display_host
    path = _path(parsed.path)
    normalized_url = urlunsplit(("https", authority, path or "/", "", ""))
    normalized_key = f"{authority}{path}" if path else authority
    return NormalizedWebsite(normalized_url, normalized_key, host)


def canonicalize_crawl_url(
    value: str, *, base_url: str | None = None, allow_sitemap: bool = False
) -> str | None:
    raw = urljoin(base_url, value) if base_url else value
    parsed = urlsplit(raw)
    scheme = parsed.scheme.casefold()
    if scheme in SKIPPED_SCHEMES or scheme not in {"http", "https"}:
        return None
    if parsed.username or parsed.password or not parsed.hostname:
        return None
    host = _network_host(parsed.hostname)
    port = _port(parsed)
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    try:
        address = ipaddress.ip_address(host)
        display_host = f"[{host}]" if address.version == 6 else host
    except ValueError:
        display_host = host
    authority = f"{display_host}:{port}" if port else display_host
    path = _path(parsed.path)
    lowered = path.casefold()

    segments = [seg for seg in lowered.split("/") if seg]
    for seg in segments:
        if (
            seg in SKIPPED_PATH_SEGMENTS
            or seg.startswith("wp-admin")
            or seg.startswith("wp-login")
        ):
            return None

    if lowered.endswith(".rss") or lowered.endswith(".atom") or lowered.endswith("/feed"):
        return None

    query_params = parse_qsl(parsed.query, keep_blank_values=False)
    for key, _ in query_params:
        folded_key = key.casefold()
        if folded_key in SEARCH_QUERY_PARAMETERS:
            return None
        if folded_key == "feed":
            return None

    if any(lowered.endswith(extension) for extension in SKIPPED_EXTENSIONS) and not (
        allow_sitemap and lowered.endswith(".xml")
    ):
        return None
    return urlunsplit((scheme, authority, path or "/", _query(parsed.query), ""))


def normalized_host(value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.hostname:
        raise URLValidationError("URL must contain a hostname")
    return _host(parsed.hostname)
