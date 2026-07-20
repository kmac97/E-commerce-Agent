# Regression check for the SSRF-safe fetch utility (backend/tools/safe_fetch.py).
# validate_url tests need real network/DNS (this environment has internet
# access -- prior pip installs confirm it). The fetch/limits tests use a
# local stdlib http.server instead of a mock library, and deliberately call
# _fetch_with_limits() directly (bypassing safe_get()'s outer validate_url
# gate) since the test server's own address is loopback -- which the gate
# is *supposed* to reject; that's tested separately and explicitly below.
# Run with: python backend/tests/test_safe_fetch.py

import asyncio
import http.server
import pathlib
import sys
import threading

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from tools.safe_fetch import (  # noqa: E402
    UnsafeURLError, validate_url, _fetch_with_limits, MAX_RESPONSE_BYTES,
)


# ── validate_url: allow/deny ──────────────────────────────────────────────

def test_allows_real_public_https_domain():
    assert validate_url("https://example.com/page") == "https://example.com/page"


def test_denies_non_https_scheme():
    for bad in ("http://example.com", "ftp://example.com", "file:///etc/passwd"):
        try:
            validate_url(bad)
            raise AssertionError(f"should have rejected {bad}")
        except UnsafeURLError:
            pass


def test_denies_localhost():
    try:
        validate_url("https://localhost/x")
        raise AssertionError("should have rejected localhost")
    except UnsafeURLError:
        pass


def test_denies_loopback_ipv4_and_ipv6():
    for bad in ("https://127.0.0.1/x", "https://[::1]/x"):
        try:
            validate_url(bad)
            raise AssertionError(f"should have rejected {bad}")
        except UnsafeURLError:
            pass


def test_denies_private_ipv4_ranges():
    for bad in ("https://10.0.0.5/x", "https://172.16.0.1/x", "https://192.168.1.1/x"):
        try:
            validate_url(bad)
            raise AssertionError(f"should have rejected {bad}")
        except UnsafeURLError:
            pass


def test_denies_link_local_and_cloud_metadata():
    # 169.254.169.254 (AWS/GCP/Azure metadata) falls in the link-local block.
    for bad in ("https://169.254.169.254/latest/meta-data/", "https://169.254.1.1/x"):
        try:
            validate_url(bad)
            raise AssertionError(f"should have rejected {bad}")
        except UnsafeURLError:
            pass


def test_denies_ipv6_unique_local():
    try:
        validate_url("https://[fc00::1]/x")
        raise AssertionError("should have rejected fc00::1")
    except UnsafeURLError:
        pass


def test_denies_unresolvable_hostname():
    try:
        validate_url("https://this-domain-should-not-exist-xyz123.invalid/x")
        raise AssertionError("should have rejected an unresolvable hostname")
    except UnsafeURLError:
        pass


# ── _fetch_with_limits: content-type, size cap, redirect re-validation ────

class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # quiet

    def do_GET(self):
        if self.path == "/small.html":
            body = b"<html><body>hello</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/image.png":
            body = b"\x89PNG fake bytes"
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/big.html":
            body = b"x" * (MAX_RESPONSE_BYTES + 1000)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/redirect-to-private":
            self.send_response(302)
            self.send_header("Location", "https://10.0.0.5/internal")
            self.end_headers()
        elif self.path == "/redirect-loop":
            self.send_response(302)
            self.send_header("Location", "/redirect-loop")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()


def _start_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _run_fetch_limit_checks():
    try:
        import httpx
    except ImportError as e:
        print(f"SKIP fetch/limits checks (httpx not installed here): {e}")
        return

    server = _start_server()
    base = f"http://127.0.0.1:{server.server_port}"

    async def _check():
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            res = await _fetch_with_limits(f"{base}/small.html", client)
            assert res.status_code == 200
            assert b"hello" in res.content
            print("  allowed: small text/html body fetched correctly")

            try:
                await _fetch_with_limits(f"{base}/image.png", client)
                raise AssertionError("should have rejected image/png content-type")
            except UnsafeURLError:
                print("  denied: disallowed content-type (image/png)")

            try:
                await _fetch_with_limits(f"{base}/big.html", client)
                raise AssertionError("should have rejected an oversized response")
            except UnsafeURLError:
                print("  denied: response over the size cap")

            try:
                await _fetch_with_limits(f"{base}/redirect-to-private", client)
                raise AssertionError("should have rejected a redirect to a private IP")
            except UnsafeURLError:
                print("  denied: redirect retargeting to a private IP (10.0.0.5)")

            try:
                await _fetch_with_limits(f"{base}/redirect-loop", client)
                raise AssertionError("should have rejected too many redirects")
            except UnsafeURLError:
                print("  denied: redirect loop past MAX_REDIRECTS")

    asyncio.run(_check())
    server.shutdown()
    print("fetch/limits checks passed")


if __name__ == "__main__":
    test_allows_real_public_https_domain()
    test_denies_non_https_scheme()
    test_denies_localhost()
    test_denies_loopback_ipv4_and_ipv6()
    test_denies_private_ipv4_ranges()
    test_denies_link_local_and_cloud_metadata()
    test_denies_ipv6_unique_local()
    test_denies_unresolvable_hostname()
    print("validate_url allow/deny tests passed")
    _run_fetch_limit_checks()
