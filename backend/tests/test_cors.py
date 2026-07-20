# Regression check for the CORS origin allowlist (backend/config.py +
# main.py's CORSMiddleware setup). Builds a minimal app with the same
# middleware config main.py uses rather than importing main.py itself
# (which needs supabase/crewai/telegram installed). Needs fastapi+httpx
# installed to run -- skips with a clear message otherwise.
# Run with: python backend/tests/test_cors.py

import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402


def test_default_allowed_origins_are_the_known_vercel_domains():
    assert config.ALLOWED_ORIGINS == [
        "https://e-commerce-agent-mu.vercel.app",
        "https://e-commerce-agent-brighttoproofingos.vercel.app",
        "https://e-commerce-agent-git-main-brighttoproofingos.vercel.app",
    ]


def _run_middleware_check():
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.testclient import TestClient
    except ImportError as e:
        print(f"SKIP middleware check (fastapi/httpx not installed here): {e}")
        return

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Api-Key"],
    )

    @app.get("/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app)

    allowed = config.ALLOWED_ORIGINS[0]
    r = client.get("/ping", headers={"Origin": allowed})
    assert r.headers.get("access-control-allow-origin") == allowed, (
        "allowed origin should get access-control-allow-origin echoed back"
    )

    r = client.get("/ping", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in r.headers, (
        "disallowed origin must not get an access-control-allow-origin header"
    )

    print("middleware check passed")


if __name__ == "__main__":
    test_default_allowed_origins_are_the_known_vercel_domains()
    print("config parsing test passed")
    _run_middleware_check()
