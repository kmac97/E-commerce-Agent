# Regression check for Phase 2.1 (backend/tools/llm_client.py). Mocks httpx
# with a queue of canned responses (one per underlying post() call) to
# exercise retry-then-succeed, retry-exhaustion-then-fallback-model, and
# total-failure paths. Patches asyncio.sleep to a no-op so retry backoffs
# (2s, 4s) don't actually slow the test down.
# Run with: python backend/tests/test_llm_client.py

import asyncio
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402
config.OPENROUTER_API_KEY = "test-key"
config.OPENROUTER_MODEL = "anthropic/claude-haiku-4.5"
config.OPENROUTER_FALLBACK_MODEL = "openai/gpt-5.6-luna"

import httpx  # noqa: E402
import tools.llm_client as llm_client  # noqa: E402

_real_sleep = asyncio.sleep  # capture before patching -- llm_client.asyncio IS this same module object
llm_client.asyncio.sleep = lambda *_a, **_kw: _real_sleep(0)  # no real backoff delay in tests


class _FakeResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        return self._json


class _FakeAsyncClient:
    responses = []  # queue: one popped per post() call, in order
    calls = []      # records the "model" field of every request made

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, _url, json=None, **_kw):
        _FakeAsyncClient.calls.append(json.get("model"))
        return _FakeAsyncClient.responses.pop(0)


httpx.AsyncClient = _FakeAsyncClient


def _ok(text):
    return _FakeResponse(200, {"choices": [{"message": {"content": text}}]})


async def _run():
    messages = [{"role": "user", "content": "hi"}]

    # Success on the first try.
    _FakeAsyncClient.responses = [_ok("hello there")]
    _FakeAsyncClient.calls = []
    reply = await llm_client.call_llm(messages)
    assert reply == "hello there"
    assert _FakeAsyncClient.calls == ["anthropic/claude-haiku-4.5"]

    # 429 then success -> retried on the SAME model, not the fallback.
    _FakeAsyncClient.responses = [_FakeResponse(429, text="rate limited"), _ok("recovered")]
    _FakeAsyncClient.calls = []
    reply = await llm_client.call_llm(messages)
    assert reply == "recovered"
    assert _FakeAsyncClient.calls == ["anthropic/claude-haiku-4.5", "anthropic/claude-haiku-4.5"]

    # Primary exhausts all retries on 500s -> falls back to the fallback model.
    _FakeAsyncClient.responses = [
        _FakeResponse(500, text="err1"),
        _FakeResponse(500, text="err2"),
        _FakeResponse(500, text="err3"),  # MAX_RETRIES=2 means 3 total attempts on primary
        _ok("fallback saved the day"),
    ]
    _FakeAsyncClient.calls = []
    reply = await llm_client.call_llm(messages)
    assert reply == "fallback saved the day"
    assert _FakeAsyncClient.calls == [
        "anthropic/claude-haiku-4.5", "anthropic/claude-haiku-4.5", "anthropic/claude-haiku-4.5",
        "openai/gpt-5.6-luna",
    ]

    # A non-retryable 400 doesn't burn retries on the primary, but still tries the fallback.
    _FakeAsyncClient.responses = [_FakeResponse(400, text="bad request"), _ok("fallback again")]
    _FakeAsyncClient.calls = []
    reply = await llm_client.call_llm(messages)
    assert reply == "fallback again"
    assert _FakeAsyncClient.calls == ["anthropic/claude-haiku-4.5", "openai/gpt-5.6-luna"]

    # Malformed 200 (no "choices") -> treated like a failure, tries fallback.
    _FakeAsyncClient.responses = [_FakeResponse(200, {"error": "weird body"}), _ok("fallback rescued")]
    _FakeAsyncClient.calls = []
    reply = await llm_client.call_llm(messages)
    assert reply == "fallback rescued"

    # Both primary and fallback exhausted -> raises LLMCallError, not a raw exception.
    _FakeAsyncClient.responses = [
        _FakeResponse(500), _FakeResponse(500), _FakeResponse(500),  # primary: 3 attempts
        _FakeResponse(500), _FakeResponse(500), _FakeResponse(500),  # fallback: 3 attempts
    ]
    try:
        await llm_client.call_llm(messages)
        raise AssertionError("expected LLMCallError")
    except llm_client.LLMCallError:
        pass

    # An explicit model= override is honoured, and no fallback needed on success.
    _FakeAsyncClient.responses = [_ok("fast tier reply")]
    _FakeAsyncClient.calls = []
    reply = await llm_client.call_llm(messages, model="anthropic/claude-haiku-4.5")
    assert reply == "fast tier reply"


if __name__ == "__main__":
    asyncio.run(_run())
    print("llm_client checks passed")
