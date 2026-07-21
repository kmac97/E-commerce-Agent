# tools/llm_client.py
# Shared OpenRouter chat-completion call for every LLM call site in the app.
# Validates the HTTP status before parsing (the ad hoc httpx blocks this
# replaces all skipped that check, so a 429/5xx body got parsed as if it were
# a real reply and failed with a confusing KeyError instead of a clear
# error), retries with backoff on 429/5xx, and falls back to
# config.OPENROUTER_FALLBACK_MODEL if the primary model/provider is down.

import asyncio
import logging

import httpx

import config

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 2  # doubles each retry: 2s, 4s
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMCallError(Exception):
    """Raised when the call fails after retries and fallback are exhausted.
    Callers decide their own fallback UX (return an error message, log and
    skip, etc.) rather than this helper silently swallowing it."""


async def call_llm(
    messages: list,
    model: str = None,
    max_tokens: int = 500,
    temperature: float = 0.7,
    timeout: float = 30,
) -> str:
    """Call OpenRouter's chat completions endpoint, return the reply text."""
    primary = model or config.OPENROUTER_MODEL
    models_to_try = [primary]
    if config.OPENROUTER_FALLBACK_MODEL and config.OPENROUTER_FALLBACK_MODEL != primary:
        models_to_try.append(config.OPENROUTER_FALLBACK_MODEL)

    last_error = None
    for attempt_model in models_to_try:
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    res = await client.post(
                        f"{config.OPENROUTER_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": attempt_model,
                            "messages": messages,
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                        },
                    )

                if res.status_code == 200:
                    data = res.json()
                    return data["choices"][0]["message"]["content"].strip()

                last_error = f"HTTP {res.status_code} from {attempt_model}: {res.text[:300]}"
                if res.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                    backoff = RETRY_BACKOFF_SECONDS * (2 ** attempt)
                    logger.warning(f"LLM call to {attempt_model} got {res.status_code}, retrying in {backoff}s")
                    await asyncio.sleep(backoff)
                    continue
                break  # non-retryable status, or retries exhausted -- try the next model

            except (KeyError, IndexError, TypeError) as e:
                # Valid response, unexpected shape (e.g. an error body with no
                # "choices") -- won't fix itself on retry, try the next model.
                last_error = f"Malformed response from {attempt_model}: {e}"
                break
            except Exception as e:
                last_error = f"{attempt_model} request failed: {e}"
                if attempt < MAX_RETRIES:
                    backoff = RETRY_BACKOFF_SECONDS * (2 ** attempt)
                    logger.warning(f"LLM call to {attempt_model} errored ({e}), retrying in {backoff}s")
                    await asyncio.sleep(backoff)
                    continue
                break

    raise LLMCallError(last_error or "LLM call failed for an unknown reason")
