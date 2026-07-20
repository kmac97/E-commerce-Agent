# Regression check for Phase 0.9 (model config reconciliation).
# Confirms config.py's defaults are the reconciled Claude-via-OpenRouter
# values, and that the three previously-hardcoded meta-llama/llama-3.3-70b
# call sites now read from config instead of a literal string.
# Run with: python backend/tests/test_model_config.py

import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402


def test_default_models_are_claude_via_openrouter():
    assert config.OPENROUTER_MODEL == "anthropic/claude-haiku-4.5"
    assert config.OPENROUTER_FAST_MODEL == "anthropic/claude-haiku-4.5"


def test_no_hardcoded_llama_model_strings_remain():
    for relpath in (
        "agents/crew.py",
        "api/agents.py",
        "tgbot/briefing.py",
    ):
        src = (BACKEND / relpath).read_text(encoding="utf-8")
        assert "meta-llama/llama-3.3-70b-instruct" not in src, (
            f"{relpath} still hardcodes the old model string instead of "
            "reading from config.OPENROUTER_FAST_MODEL"
        )


def test_fast_model_call_sites_reference_config():
    # Each of these files should call OPENROUTER_FAST_MODEL at least once
    # now, rather than a literal model string, for the extraction task.
    checks = {
        "agents/crew.py": "config.OPENROUTER_FAST_MODEL",
        "api/agents.py": "cfg.OPENROUTER_FAST_MODEL",
        "tgbot/briefing.py": "config.OPENROUTER_FAST_MODEL",
    }
    for relpath, needle in checks.items():
        src = (BACKEND / relpath).read_text(encoding="utf-8")
        assert needle in src, f"{relpath} does not reference {needle}"


if __name__ == "__main__":
    test_default_models_are_claude_via_openrouter()
    test_no_hardcoded_llama_model_strings_remain()
    test_fast_model_call_sites_reference_config()
    print("model config reconciliation checks passed")
