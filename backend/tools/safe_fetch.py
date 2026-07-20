# tools/safe_fetch.py
# Shared SSRF-safe URL validation + fetch for endpoints that fetch
# user-supplied or arbitrary URLs (api/agents.py's import-product and
# spy-store).
#
# ponytail: DNS is resolved and validated before connecting, but httpx does
# its own resolution again at actual connect time -- a narrow DNS-rebinding
# window remains between our check and the real TCP connect. Full protection
# needs pinning the connection to the resolved IP via a custom transport.
# Not worth that complexity for a personal store's product-import feature;
# revisit if this ever handles higher-stakes traffic.

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2MB
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml", "application/json")
REQUEST_TIMEOUT = 12  # per-operation (connect/read/write) httpx timeout
TOTAL_TIMEOUT = 20  # wall-clock cap across all redirects combined


class UnsafeURLError(Exception):
    pass


@dataclass
class SafeResponse:
    status_code: int
    headers: httpx.Headers
    content: bytes

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self):
        import json
        return json.loads(self.content)


def _check_ip(ip_str: str, hostname: str):
    ip = ipaddress.ip_address(ip_str)
    if (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    ):
        raise UnsafeURLError(f"{hostname} resolves to a disallowed address ({ip_str})")


def validate_url(url: str) -> str:
    """SSRF gate: https-only, resolves the hostname, and rejects it if any
    resolved address is loopback/private/link-local/reserved/multicast/
    unspecified (this also catches cloud metadata IPs like 169.254.169.254,
    which fall in the link-local range -- and defeats decimal/octal/hex IP
    obfuscation tricks, since we check the *resolved* address, not the
    literal hostname string). Returns the URL unchanged if it passes, else
    raises UnsafeURLError.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise UnsafeURLError("only https:// URLs are allowed")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("no hostname in URL")
    if hostname.lower() == "localhost":
        raise UnsafeURLError("localhost is not allowed")

    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise UnsafeURLError(f"could not resolve {hostname}: {e}")

    for *_, sockaddr in addrinfo:
        _check_ip(sockaddr[0], hostname)

    return url


async def _fetch_with_limits(url: str, client: httpx.AsyncClient) -> SafeResponse:
    """Fetches url, following redirects manually so each hop gets
    re-validated, and enforcing content-type and response-size limits.

    Does NOT validate the initial url's scheme/host -- callers must do that
    first (safe_get does). Split out so this fetch/limits logic is testable
    against a local test server without the SSRF gate rejecting
    http://127.0.0.1 in the test itself.
    """
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        async with client.stream("GET", current_url) as res:
            if res.is_redirect:
                location = res.headers.get("location")
                if not location:
                    raise UnsafeURLError("redirect with no Location header")
                current_url = validate_url(str(httpx.URL(current_url).join(location)))
                continue

            content_type = res.headers.get("content-type", "").split(";")[0].strip().lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise UnsafeURLError(f"disallowed content-type: {content_type or 'unknown'}")

            content_length = res.headers.get("content-length")
            if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                raise UnsafeURLError("response exceeds size limit")

            body = bytearray()
            async for chunk in res.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise UnsafeURLError("response exceeded size limit")

            return SafeResponse(status_code=res.status_code, headers=res.headers, content=bytes(body))

    raise UnsafeURLError("too many redirects")


async def safe_get(url: str) -> SafeResponse:
    """SSRF-safe GET: validates the URL (scheme + resolved-IP range check),
    then fetches with per-hop redirect re-validation, a response-size cap,
    a content-type check, and an overall wall-clock timeout."""
    validated = validate_url(url)

    async def _run():
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=False,
            headers={"User-Agent": "Mozilla/5.0"},
        ) as client:
            return await _fetch_with_limits(validated, client)

    return await asyncio.wait_for(_run(), timeout=TOTAL_TIMEOUT)
