# Regression check for Phase 2.3 (the research-only Sonnet 5 tier split).
# Confirms agents/researcher.py's get_llm() actually uses
# OPENROUTER_RESEARCH_MODEL, and that every other call site touched in
# Phase 2.1 still reads the cheaper OPENROUTER_MODEL/OPENROUTER_FAST_MODEL --
# i.e. the split didn't accidentally widen to call sites the user didn't
# choose to upgrade.
# Run with: python backend/tests/test_model_tiers.py

import pathlib
import sys
import types

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402


def test_defaults():
    assert config.OPENROUTER_MODEL == "anthropic/claude-haiku-4.5"
    assert config.OPENROUTER_FAST_MODEL == "anthropic/claude-haiku-4.5"
    assert config.OPENROUTER_RESEARCH_MODEL == "anthropic/claude-sonnet-5"


def test_researcher_uses_research_model():
    # Stub crewai just enough to import agents/researcher.py for real.
    crewai_stub = types.ModuleType("crewai")

    class _Agent:
        def __init__(self, *a, **kw):
            pass

    class _Task:
        def __init__(self, *a, **kw):
            pass

    captured = {}

    class _LLM:
        def __init__(self, model, **kw):
            captured["model"] = model

    crewai_stub.Agent = _Agent
    crewai_stub.Task = _Task
    crewai_stub.LLM = _LLM
    sys.modules["crewai"] = crewai_stub

    crewai_tools_stub = types.ModuleType("crewai_tools")

    class _TavilySearchTool:
        def __init__(self, *a, **kw):
            pass

    crewai_tools_stub.TavilySearchTool = _TavilySearchTool
    sys.modules["crewai_tools"] = crewai_tools_stub

    import agents.researcher as researcher
    researcher.get_llm()
    assert captured["model"] == f"openrouter/{config.OPENROUTER_RESEARCH_MODEL}"
    assert captured["model"] == "openrouter/anthropic/claude-sonnet-5"


def test_other_call_sites_unchanged():
    """Every Phase 2.1 call site must still read the cheap tiers, not have
    silently widened onto OPENROUTER_RESEARCH_MODEL."""
    checks = {
        "tgbot/commands.py": "cfg.OPENROUTER_MODEL",
        "api/agents.py": "cfg.OPENROUTER_MODEL",
        "tgbot/briefing.py": "config.OPENROUTER_FAST_MODEL",
        "tgbot/store_monitor.py": "config.OPENROUTER_MODEL",
        "agents/trending.py": "config.OPENROUTER_MODEL",
        "agents/crew.py": "config.OPENROUTER_FAST_MODEL",
    }
    for relpath, needle in checks.items():
        src = (BACKEND / relpath).read_text(encoding="utf-8")
        assert needle in src, f"{relpath} no longer references {needle}"
        assert "OPENROUTER_RESEARCH_MODEL" not in src, (
            f"{relpath} references OPENROUTER_RESEARCH_MODEL -- only "
            "agents/researcher.py should use the research tier"
        )


if __name__ == "__main__":
    test_defaults()
    test_researcher_uses_research_model()
    test_other_call_sites_unchanged()
    print("model tier split checks passed")
