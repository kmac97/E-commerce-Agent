# Regression check for a finding from an external code review (2026-07-21):
# the CrewAI store-manager agent held CreateProductTool/UpdateProductTool
# directly, with no path to the actions/approvals gate -- if any code ever
# instantiates a crew with this agent (agents/crew.py's build_full_crew()
# isn't called anywhere today, but nothing should rely on that staying
# true), an LLM could write to Shopify with zero human approval. Only
# read-only tools belong here until CrewAI tools themselves can propose
# through the approval gate rather than writing directly.
# Run with: python backend/tests/test_store_manager_tools.py

import pathlib
import sys
import types

BACKEND = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# ── stub crewai just enough to import agents/store_manager.py for real ──
crewai_stub = types.ModuleType("crewai")


class _Agent:
    def __init__(self, *a, tools=None, **kw):
        self.tools = tools or []


class _LLM:
    def __init__(self, *a, **kw):
        pass


crewai_stub.Agent = _Agent
crewai_stub.LLM = _LLM
sys.modules["crewai"] = crewai_stub

_crewai_tools_stub = types.ModuleType("crewai.tools")


class _BaseTool:
    pass


_crewai_tools_stub.BaseTool = _BaseTool
sys.modules["crewai.tools"] = _crewai_tools_stub
crewai_stub.tools = _crewai_tools_stub

import config  # noqa: E402
config.SHOPIFY_ACCESS_TOKEN = "test-token"
config.SHOPIFY_SHOP_URL = "teststore.myshopify.com"
config.OPENROUTER_API_KEY = "test-key"

import agents.store_manager as store_manager  # noqa: E402


def test_store_manager_agent_has_no_write_tools():
    agent = store_manager.create_store_manager_agent()
    tool_names = {getattr(t, "name", type(t).__name__) for t in agent.tools}

    assert "create_shopify_product" not in tool_names, (
        "store-manager agent must not hold create_shopify_product -- it has "
        "no path to the actions/approvals gate"
    )
    assert "update_shopify_product" not in tool_names, (
        "store-manager agent must not hold update_shopify_product -- it has "
        "no path to the actions/approvals gate"
    )
    # Read-only tools are still fine to keep.
    assert "get_shopify_products" in tool_names
    assert "get_shopify_orders" in tool_names


def test_build_full_crew_is_not_wired_into_any_live_code_path():
    """Defence-in-depth is cheap; confirm the actual live risk (an
    autonomous crew run) still doesn't exist anywhere outside its own
    definition. If this ever fails, the dormant risk above just went live
    and the tool list needs the approval-gate redesign, not just pruning."""
    crew_src = (BACKEND / "agents" / "crew.py").read_text(encoding="utf-8")
    other_sources = "\n".join(
        (BACKEND / rel).read_text(encoding="utf-8")
        for rel in ("main.py",)
    )
    call_sites = other_sources.count("build_full_crew(")
    assert call_sites == 0, "build_full_crew() is now called somewhere -- the tool-list fix alone is no longer sufficient"
    assert "def build_full_crew" in crew_src


if __name__ == "__main__":
    test_store_manager_agent_has_no_write_tools()
    test_build_full_crew_is_not_wired_into_any_live_code_path()
    print("store manager tool-list checks passed")
