# Regression check for the rate limiter (backend/api/rate_limit.py).
# Builds a minimal app wired the same way main.py wires slowapi, rather than
# importing main.py itself (needs supabase/crewai/telegram installed).
# Needs fastapi+slowapi installed to run -- skips with a clear message
# otherwise. Run with: python backend/tests/test_rate_limit.py

import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


def _run_check():
    try:
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient
        from slowapi import _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.middleware import SlowAPIMiddleware
        from api.rate_limit import limiter
    except ImportError as e:
        print(f"SKIP rate limit check (deps not installed here): {e}")
        return

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/limited")
    @limiter.limit("3/minute")
    async def limited(request: Request):
        return {"ok": True}

    client = TestClient(app)

    # First 3 requests (even from different simulated IPs -- key_func is
    # global, not per-IP, so they all share one bucket) succeed.
    for i, ip in enumerate(["1.1.1.1", "2.2.2.2", "3.3.3.3"]):
        r = client.get("/limited", headers={"X-Forwarded-For": ip})
        assert r.status_code == 200, f"request {i} from {ip} should succeed, got {r.status_code}"

    # 4th request, from yet another IP, is still blocked -- proves the limit
    # is global (total spend cap), not per-client.
    r = client.get("/limited", headers={"X-Forwarded-For": "4.4.4.4"})
    assert r.status_code == 429, f"4th request should be rate-limited, got {r.status_code}"

    print("rate limit check passed (global bucket, not per-IP)")


if __name__ == "__main__":
    _run_check()
