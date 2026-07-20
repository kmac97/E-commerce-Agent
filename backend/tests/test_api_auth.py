# Regression check for the dashboard API key gate (backend/api/auth.py).
# The comparison-logic tests run anywhere with no dependencies. The
# dependency-function check needs fastapi installed (VPS / a real venv) --
# it's skipped with a clear message otherwise, not silently marked as passed.
# Run with: python backend/tests/test_api_auth.py

import asyncio
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from api.auth import is_valid_api_key  # noqa: E402


def test_valid_key_matches():
    assert is_valid_api_key("secret123", "secret123") is True


def test_wrong_key_rejected():
    assert is_valid_api_key("wrong", "secret123") is False


def test_missing_provided_key_rejected():
    assert is_valid_api_key(None, "secret123") is False


def test_missing_expected_key_rejected():
    assert is_valid_api_key("secret123", None) is False


def test_both_missing_rejected():
    assert is_valid_api_key(None, None) is False


def test_empty_strings_rejected():
    assert is_valid_api_key("", "") is False


def _run_dependency_check():
    """Exercises require_api_key() directly -- no app boot, no env vars needed."""
    try:
        from fastapi import HTTPException
        import config
        from api.auth import require_api_key
    except ImportError as e:
        print(f"SKIP dependency check (fastapi not installed here): {e}")
        return

    async def _check():
        config.API_KEY = "test-key-123"

        for bad_key in (None, "wrong"):
            try:
                await require_api_key(x_api_key=bad_key)
                raise AssertionError(f"expected 401 for key={bad_key!r}")
            except HTTPException as e:
                assert e.status_code == 401

        await require_api_key(x_api_key="test-key-123")  # must not raise

    asyncio.run(_check())
    print("dependency check passed")


if __name__ == "__main__":
    test_valid_key_matches()
    test_wrong_key_rejected()
    test_missing_provided_key_rejected()
    test_missing_expected_key_rejected()
    test_both_missing_rejected()
    test_empty_strings_rejected()
    print("core key-comparison tests passed")
    _run_dependency_check()
