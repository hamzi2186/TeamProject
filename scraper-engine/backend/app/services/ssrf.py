import asyncio
import ipaddress
import socket
import time
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from app.services.urls import URLValidationError

Resolver = Callable[[str, int], Awaitable[list[str]]]
BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.google",
    "instance-data",
}

_DNS_CACHE: dict[tuple[str, int], tuple[float, list[str]]] = {}
_DNS_CACHE_TTL = 60.0


class UnsafeTargetError(URLValidationError):
    pass


async def system_resolver(host: str, port: int) -> list[str]:
    def resolve() -> list[str]:
        now = time.monotonic()
        cached = _DNS_CACHE.get((host, port))
        if cached is not None and cached[0] > now:
            return cached[1]
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
                results = sorted({record[4][0] for record in records})
                if results:
                    _DNS_CACHE[(host, port)] = (time.monotonic() + _DNS_CACHE_TTL, results)
                    return results
            except (OSError, socket.gaierror) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.15 * (attempt + 1))
        if last_error:
            raise last_error
        return []

    return await asyncio.to_thread(resolve)


def _validate_address(value: str) -> None:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise UnsafeTargetError("Website hostname resolved to an invalid address") from exc
    if not address.is_global:
        raise UnsafeTargetError("Website resolves to a non-public network address")
    if address in ipaddress.ip_network("169.254.169.254/32"):
        raise UnsafeTargetError("Cloud metadata endpoints are not allowed")


async def validate_public_url(url: str, *, resolver: Resolver = system_resolver) -> list[str]:
    parsed = urlsplit(url)
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise UnsafeTargetError("Only HTTP and HTTPS targets are allowed")
    if parsed.username or parsed.password:
        raise UnsafeTargetError("Target URLs must not contain credentials")
    host = (parsed.hostname or "").rstrip(".").casefold()
    if not host:
        raise UnsafeTargetError("Target URL must contain a hostname")
    if (
        host in BLOCKED_HOSTS
        or host.endswith(".localhost")
        or host.endswith(".local")
        or host.endswith(".internal")
        or host.endswith(".home.arpa")
    ):
        raise UnsafeTargetError("Internal hostnames are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        _validate_address(host)
        return [host]
    try:
        addresses = await resolver(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except (OSError, socket.gaierror) as exc:
        raise URLValidationError("Website hostname could not be resolved") from exc
    if not addresses:
        raise URLValidationError("Website hostname did not resolve to an address")
    for address in addresses:
        _validate_address(address)
    return addresses
