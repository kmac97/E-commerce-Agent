# Build Plan — Security Hardening & Operating Kernel

For use with Claude Code. Written after reading the actual source (`main.py`, `config.py`, all of `backend/agents/`, `backend/api/`, `backend/tgbot/`, `backend/database/client.py`, `backend/tools/`, `frontend/app.js`, `frontend/index.html`) and cross-checking a second AI review (GPT) of the same repo against that source.

---

## How this compares to the GPT review

GPT's review is accurate. Nearly every P0 it raised is independently confirmed against the actual files, not just plausible-sounding:

- **No auth on any route** — confirmed. `main.py` sets `allow_origins=["*"]`, and none of `agents.py`, `research.py`, `dashboard.py`, `shopify_auth.py` have an auth dependency. The `allow_credentials=False` comment shows whoever wrote it knew wildcard+credentials is disallowed by spec — but turning credentials off doesn't close the hole, it just avoids a browser-level CORS error. The API is fully open to anyone who finds the URL.
- **Shopify OAuth route is unsafe** — confirmed, and worse in detail than a summary conveys: `shopify_auth.py` hardcodes the VPS IP and shop domain, uses `http://` not `https://` for the callback, builds the authorize URL with no `state` param at all, never checks the Shopify HMAC on callback, and the callback handler prints the live access token into the HTTP response *and* into a shell command shown in plaintext in the browser. If that URL was ever hit for real, treat the token as burned.
- **Telegram has no owner check** — confirmed. `bot.py` registers command handlers and a catch-all text handler with no filter comparing `update.effective_chat.id` to `config.TELEGRAM_CHAT_ID` anywhere in `commands.py`.
- **SSRF in `/import-product` and `/spy-store`** — confirmed. Both fetch arbitrary user-supplied URLs with `httpx`, `follow_redirects=True`, no scheme restriction, no private/loopback/metadata-IP blocking, and the fetched page text is fed straight into an LLM prompt.
- **AI writes to Shopify with no approval step** — confirmed, and this is the one I'd already flagged: `crew.py` auto-creates a Shopify draft the moment a research score hits 7+, and `store_monitor.py`'s `optimise_product_listing` rewrites a live product's title/description on Shopify directly from an LLM call with no preview, no diff, no confirmation.
- **`search_tools.py` references `config.SERPER_BASE_URL`, which doesn't exist** — confirmed, would crash if the (currently dead) code path were ever called.
- **`api/agents.py` calls `logger.error(...)` with no `logger` defined in that module** — confirmed, would raise `NameError` the first time an OpenRouter call in `chat_with_max` fails.
- **Sync Supabase `.execute()` calls inside `async def` route handlers** — confirmed in `database/client.py`; every DB call blocks the event loop.
- **Model choice disagrees across files** — confirmed: root `.env.example`/README say Hermes-3, `backend/config.py` defaults to `perplexity/sonar-pro`, and three separate files (`crew.py`, `agents.py`, `briefing.py`) hardcode `meta-llama/llama-3.3-70b-instruct` directly instead of reading from config.

**Where I'd push back or refine:**

1. **The Shopify GraphQL point is real but slightly overstated for this app.** I checked: REST Admin API has been legacy since October 1, 2024, and *new public apps* have been required to use GraphQL since April 1, 2025 — but this is a private/custom app for one store, not a public App Store listing, so it isn't contractually forced onto GraphQL today. That said, REST is capped at 100 variants per product against GraphQL's 2048, Shopify ships a new API version every quarter and only supports each for 12 months, and REST is on a deprecation clock regardless. Treat it as "do it before it becomes a fire drill," not P0-this-week — it comes after the security fixes below, not before them.
2. **The 16-table schema and full Store Director / Workflow Engine / Policy Layer architecture is the right shape but oversized for where you are.** That's an architecture for running many stores with a team behind them. You're one operator validating one store on a sub-$200/month budget. Building all of `stores`, `store_policies`, `jobs`, `agent_runs`, `model_calls`, `tool_calls`, `actions`, `approvals`, `decisions`, `evidence`, `sources`, `product_candidates`, `supplier_quotes`, `experiments`, `metric_snapshots`, `alerts`, `incidents` before you've shipped a single sale risks building a platform instead of a store. Below I trim this to the four tables that actually gate risk (`actions`, `approvals`, `audit_log`, `jobs`) and defer the rest until you're actually replicating to store #2 or need that level of trace/analytics.
3. **Redis + ARQ/Dramatiq for durable jobs is more infrastructure than a single VPS running one store needs right now.** A Postgres/Supabase-backed job table with a polling worker loop gets you durability and dedupe without adding a new service to operate and pay for. Move to Redis-backed queueing later if job volume actually requires it.
4. **Model routing table:** GPT-5.6 (Sol/Terra/Luna) and the Claude Sonnet 5/Opus 4.8/Haiku 4.5 pricing it cites both check out as of July 2026. Given you're building this in Claude Code and already in the Claude ecosystem, I'd flip GPT's default-to-OpenAI framing: lead with Claude (Haiku 4.5 for extraction/classification, Sonnet 5 for research synthesis and drafting, Opus 4.8 as reviewer on the rare high-risk/high-spend decision), keep one OpenAI or Perplexity model as fallback for redundancy. Functionally equivalent to what GPT proposed, just reordered around the tools you're actually using to build this.

Everything else in the GPT review — reliability issues, the response-status-code gaps, the lack of shared retry/timeout policy, loose `>=` dependency ranges — is accurate and worth doing, just sequenced below.

---

## Phase 0 — Lock it down (do this before touching any new feature)

Nothing in Phase 1+ matters if the backend stays wide open. This phase is pure defense, no new capabilities.

1. **Kill the exposed OAuth route.** Disable or delete `backend/api/shopify_auth.py`'s router registration in `main.py` immediately. Rotate the Shopify access token in the Shopify admin now, on the assumption the old one may already be exposed (it was displayed in a browser response and a copy-pasted shell command). Rebuild OAuth later per Phase 3, correctly.
2. **Add auth to every API route.** Simplest fix that fits a one-operator system: a shared-secret header (e.g. `X-Api-Key`) checked via a FastAPI `Depends()` on every router in `main.py` (`agents`, `research`, `dashboard`). Set `allow_origins` to your actual dashboard domain only, not `"*"`. Add basic rate limiting (`slowapi` or similar) on the research/agent-trigger endpoints so a leaked key can't be used to burn your LLM/search budget.
3. **Restrict Telegram to you.** Add one decorator in `commands.py` that checks `update.effective_chat.id == int(config.TELEGRAM_CHAT_ID)` and silently drops anything else, applied to every command handler and `handle_message`.
4. **Fix the SSRF surface.** In `api/agents.py`, both `import_product_from_url` and `spy_competitor_store` need: `https://` only, DNS resolution + reject private/loopback/link-local/metadata ranges (`169.254.169.254` etc.), no automatic redirect following (or revalidate the redirect target), a response size cap, and a content-type check before parsing.
5. **Sanitize the frontend.** In `app.js`, anywhere research text, product notes, task output, or chat replies are inserted via `innerHTML`, switch to `textContent` for plain values or run through DOMPurify with raw HTML disabled for anything markdown-rendered.
6. **Fix the two live bugs.** Remove or repair `backend/tools/search_tools.py` (dead code referencing a config var that doesn't exist — either delete it since Tavily replaced it, or fix it if you want Serper back as a fallback search provider). Add `logger = logging.getLogger(__name__)` to `backend/api/agents.py`.
7. **Pick one model source of truth.** Decide the default model now (recommendation: Claude Haiku 4.5 for cheap/fast tasks, Sonnet 5 for research — see Phase 2), update `backend/config.py`, `.env.example`, `backend/.env.example`, and README so they agree, and replace the three hardcoded `meta-llama/llama-3.3-70b-instruct` references with a config-driven call.
8. **Delete the legacy v1 prototype.** Root-level `assistant.py`, `modules/*.py`, `utils/*.py`, `data/` are superseded stubs not used by `backend/` — remove them so nobody (human or AI) mistakes them for the real system.

Nothing ships past this phase until it's done. Don't connect ads, Gmail, or anything that spends money or emails customers before Phase 0 is closed out — same conclusion GPT reached, and it's correct.

---

## Phase 1 — Approval gate + durable jobs

This is the piece that was missing against your own stated preference (approve everything before it happens) and against GPT's "operating kernel" — trimmed to four tables instead of sixteen.

**New tables (Supabase):**

- `actions` — a proposed action: type (`create_shopify_product`, `update_shopify_product`, `create_ad_campaign`, ...), payload, proposing agent, risk level, status (`proposed`/`approved`/`rejected`/`executed`/`failed`), idempotency key.
- `approvals` — links to an `action`, records who approved/rejected and when, and the reason on rejection (so it can feed back into the next agent attempt, per the original plan).
- `audit_log` — append-only record of every action's full lifecycle: proposed → approved → executed → result, with before/after state for anything that touched Shopify.
- `jobs` — a durable queue row per background task (research run, product drop, store monitor) with status, attempt count, and a `locked_by`/`locked_at` pair so a restart doesn't silently drop or double-run work. A simple polling worker (a loop in its own process, or a scheduled task) claims rows instead of relying on `BackgroundTasks`/`asyncio.create_task`, which die with the web process.

**Code changes:**

- `crew.py`'s auto-Shopify-draft-on-score-7+ becomes: write an `actions` row with status `proposed`, send the Telegram Approve/Reject buttons, only call `_auto_create_shopify_draft` after an `approvals` row exists. (Draft-only creation could reasonably stay auto-approved once you trust the pipeline — but wire the gate in now and loosen it deliberately later, don't skip building it.)
- `store_monitor.py`'s `optimise_product_listing` becomes: propose the new title/description as an `actions` row with a before/after diff sent to Telegram, execute only on approval.
- Research task execution (`run_research_task`) and the cron jobs (`briefing.py`, `product_drop.py`, `store_monitor.py`) move from `BackgroundTasks`/`asyncio.create_task` onto the `jobs` table + worker loop.

Defer `stores`, `store_policies`, `model_calls`, `tool_calls`, `evidence`, `sources`, `product_candidates`, `supplier_quotes`, `experiments`, `metric_snapshots`, `alerts`, `incidents` until you're either replicating to a second store or find you actually need that granularity of trace data — adding them later is a migration, not a redesign, because `actions`/`approvals`/`audit_log` already carry the core shape.

---

## Phase 2 — Reliability cleanup

- Wrap every LLM HTTP call in one shared helper: checks `res.status_code` before parsing, retries with backoff on 429/5xx, has a consistent timeout, and supports a fallback model/provider. Replace the repeated ad hoc `httpx` blocks in `crew.py`, `agents.py`, `briefing.py`, `store_monitor.py`, `trending.py` with calls to it.
- Fix the sync-inside-async Supabase calls in `database/client.py` — either wrap `.execute()` calls in `run_in_executor`, or switch to Supabase's async client if the installed version supports it.
- Centralize model routing by task tier instead of one global model:
  - Extraction/classification (product-detail extraction, JSON parsing tasks currently hardcoded to Llama 3.3): **Claude Haiku 4.5**.
  - Research synthesis, listing drafts, chat with Max: **Claude Sonnet 5**.
  - Any decision that touches real money (ad budget approval, pricing changes above a threshold) once Phase 5 exists: **Claude Opus 4.8** as a second opinion before execution, not as the default.
  - Keep one non-Anthropic model configured as a fallback for redundancy if a provider has an outage.
- Pin dependency versions (`requirements.txt`) instead of open `>=` ranges; commit a lock file.

---

## Phase 3 — Shopify: OAuth done right, then GraphQL

- Rebuild OAuth (only after Phase 0 disables the old route): HTTPS callback, real `state` validation, Shopify HMAC verification on the callback, shop-domain allowlist, encrypted token storage server-side, token never returned to the browser, minimum required scopes only.
- Migrate Shopify calls from REST to GraphQL, read operations first (`get_shopify_products`, `get_shopify_orders`, `get_shopify_inventory` in `shopify_tools.py`), then writes (`create_shopify_product`, `update_shopify_product`) once reads are solid. Not because REST breaks tomorrow for a private app, but because it's already legacy, capped at 100 variants/product, and the migration is easier to do deliberately now than under pressure later.

---

## Phase 4 — Monitoring & support

- Move from polling (store monitor cron) to Shopify webhooks where they exist (orders, inventory) for faster, cheaper signal.
- Wire the Support agent to real tools (`email_tools.py`, `review_tools.py` are still Phase 5 stubs) — draft-only, routed through the same `actions`/`approvals` gate, no auto-send.

---

## Phase 5 — Marketing & spend

Only after Phases 0–2 are solid: Meta Ads integration (`ads_tools.py` is currently all stubs), with every campaign creation and budget change going through the approval gate, hard daily/monthly spend caps enforced in code (not just policy), and the Meta-only / TikTok-deferred budget guidance from the original master plan (`AI_Store_Master_Plan.md`) still holding — that budget math doesn't change based on this review.

---

## Suggested order of operations in Claude Code

1. Point Claude Code at this file plus the actual repo and start with Phase 0, item by item — it's small, mechanical, and each item is independently testable.
2. Rotate the Shopify token and confirm the old OAuth route is unreachable before doing anything else, even before the rest of Phase 0.
3. Phase 1's four tables and the approval-gate rewiring is the next meaningful chunk — it's the one architectural piece both reviews agree is missing and that your stated approval-first preference depends on.
4. Phases 2–5 can be sequenced or reprioritized based on what you actually want to do next (e.g. if launching real ads is the near-term goal, Phase 2's model-routing cleanup and Phase 1's approval gate are the prerequisites, not Phase 3's GraphQL migration).
