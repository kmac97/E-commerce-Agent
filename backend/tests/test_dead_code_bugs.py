# Regression check for the two Phase 0.8 bugs:
#  1. backend/tools/search_tools.py referenced config.SERPER_BASE_URL, which
#     doesn't exist -- dead code (nothing imported it), deleted rather than
#     fixed since Tavily already replaced it.
#  2. backend/api/agents.py called logger.error(...) in chat_with_max with no
#     logger defined anywhere in the module -- a NameError waiting to happen
#     the first time an OpenRouter call returned a malformed response.
# Run with: python backend/tests/test_dead_code_bugs.py

import logging
import pathlib
import sys
import types

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


def test_search_tools_deleted():
    assert not (BACKEND / "tools" / "search_tools.py").exists(), (
        "backend/tools/search_tools.py exists again -- it referenced "
        "config.SERPER_BASE_URL, which doesn't exist, and nothing imports it."
    )


def test_agents_module_has_a_real_logger():
    # Stub agents.crew so this doesn't need crewai installed just to check
    # for a module-level `logger` attribute.
    agents_pkg = types.ModuleType("agents")
    agents_pkg.__path__ = []
    crew_stub = types.ModuleType("agents.crew")

    async def run_research_task(*a, **kw):
        pass

    crew_stub.run_research_task = run_research_task
    sys.modules["agents"] = agents_pkg
    sys.modules["agents.crew"] = crew_stub

    import api.agents as agents_mod

    assert hasattr(agents_mod, "logger"), "api/agents.py has no module-level `logger`"
    assert isinstance(agents_mod.logger, logging.Logger), (
        "api/agents.py's `logger` isn't a real logging.Logger instance"
    )


if __name__ == "__main__":
    test_search_tools_deleted()
    test_agents_module_has_a_real_logger()
    print("dead-code bug regression checks passed")
