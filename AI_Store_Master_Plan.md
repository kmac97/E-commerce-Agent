# AI-Run E-Commerce Store — Master Business & Technical Plan

Prepared for Kaine Macgregor — E-commerce Assistant project
July 20, 2026

*AI operates the business end-to-end — research, product, pricing, ads, and copy — while every action that spends money or goes live publicly is queued for your approval on Telegram before it happens.*

---

## 1. Executive Summary

This plan turns the existing E-commerce Assistant repo into an AI-operated store: an agent system that researches the niche, picks the product and business model, writes the store copy, drafts and (once approved) runs ads, monitors performance, and reports back to you — while you act purely as the approver and final decision-maker, not the operator.

**Your role:** approve or reject what the AI proposes, via Telegram or the dashboard. You are not writing product descriptions, researching suppliers, or building ad campaigns by hand.

**The AI's role:** everything else — niche and product research, competitor analysis, pricing, store setup, ad copy and campaign structure, customer support drafts, and daily/weekly performance reporting.

**Budget reality:** you set a combined budget of under $200/month for tools plus ad spend. Section 3 shows this is workable — roughly $45–$60/month in tooling, leaving $140–$155/month for real ad testing on Meta. TikTok Ads is not viable at this budget (its platform minimum alone is ~$1,500/month) and is deferred to a later phase once the store is profitable.

**Why this plan is different from the current README:** the existing repo already has the right bones (CrewAI-style agents, Supabase, Telegram, Shopify, Meta/TikTok tool stubs). This plan doesn't replace that architecture — it makes three concrete decisions the original scaffold left open: which model powers the agents, what the approval workflow actually looks like, and which channels are realistic on this budget.

> Pricing and platform-policy figures below were checked via live web search on July 20, 2026. Sources are listed in Appendix C. Platform minimums, model pricing, and tool pricing change — re-verify before committing spend.

---

## 2. Operating Model — How Human + AI Split the Work

The system runs on a single rule: the AI can think, draft, and prepare anything it wants at any time. It cannot spend money or publish anything publicly without your explicit approval. This is the starting posture you chose, with a clear path to loosening it once the AI has a track record.

### 2.1 Three-tier autonomy model

| Tier | What it means | When to move here |
|---|---|---|
| **Tier 0 — Approve everything (start here)** | AI drafts research, listings, ad copy, and campaigns. Nothing goes live and no money is spent until you tap Approve in Telegram. | Day 1. Stay here for at least the first 30 days or first $500 of cumulative ad spend, whichever is longer. |
| **Tier 1 — Budget-capped autonomy** | AI can act freely within a pre-set daily/monthly cap (e.g. auto-approve ad spend under $10/day per campaign, auto-publish listings under a review checklist). Anything above the cap still needs approval. | Once you've approved 20+ AI decisions and its judgment looks sound — typically 4–8 weeks in. |
| **Tier 2 — Full autonomy** | AI runs ads, pricing, and listings independently. You receive reports, not approval requests. | Only after the store is profitable and Tier 1 has been validated for a full quarter. Not part of this initial build. |

You selected Tier 0 to start. The codebase should support all three tiers via one config flag (Section 5.4) so moving up later is a settings change, not a rebuild.

### 2.2 What "approval" looks like day to day

- The AI completes a research or drafting task and posts a summary to Telegram with Approve / Reject / Edit buttons.
- Nothing is marked "live" in the database until you approve — the `agent_tasks` and `decisions` tables (already in the schema) track this status.
- Rejections are logged with your reason, and that reason is fed back into the agent's next attempt — this is how the AI actually improves instead of repeating the same mistake.
- A weekly digest (Sunday evening) shows everything approved, rejected, and pending — so nothing sits stale in your queue.

---

## 3. Budget Reality Check (Under $200/month)

This is the most important section to get right — an "AI-run store" plan that ignores platform minimums fails in week one. Figures below are current as of July 2026.

### 3.1 Fixed tooling costs

| Item | Monthly cost | Notes |
|---|---|---|
| Shopify (Basic plan) | $29 (annual billing) – $39 (monthly) | 3-day free trial, then often a discounted first-3-months rate. Start on monthly billing until the niche is validated, switch to annual once committed. |
| LLM API (agent brain) | $10–$25 (usage-based) | Recommend Claude Haiku 4.5 (~$1 input / $5 output per million tokens) over the repo's original Hermes-3-via-OpenRouter default — similar cost, more predictable tool-calling. See Section 5.2. |
| VPS hosting (Hostinger or similar) | $5–$10 | Cheapest KVM/VPS tier is enough for Phases 1–4. |
| Domain name | ~$1 (amortized) | $10–$15/year. |
| Supabase | $0 to start | Free tier (500MB, 2 projects) covers Phases 1–3. Free projects pause after 7 days of inactivity — the Telegram bot's scheduled daily briefing keeps it active. Budget $25/mo once you outgrow it. |
| Serper (web search for research agent) | $0 to start | Free tier = 2,500 searches/month, plenty for niche/competitor research cadence in Phase 2. |
| Telegram, Vercel | $0 | Both free at this scale. |

**Tooling subtotal: roughly $45–$60/month during build and validation (Phases 1–3).**

### 3.2 Ad spend — what's actually achievable

| Platform | Platform technical minimum | Realistic minimum for usable data | Fits the budget? |
|---|---|---|---|
| Meta (Facebook/Instagram) | $1/day (impressions) or $5/day (conversions) | $5–$15/day to start collecting signal | **Yes** — this is the ads channel for Phase 4. |
| TikTok Ads | $50/day per campaign, $20/day per ad group | ~$620+ for a single 31-day ad group to exit the learning phase | **No**, not on this budget. Defer until the store is profitable and you can allocate $500+/month specifically. |

**Recommendation:** Meta only for Phase 4. Budget $5–10/day ($150–300/month) once the tooling subtotal is covered — at the low end ($5/day = $150/mo) this fits inside the $200/mo ceiling alongside lean tooling. Realistically, expect the first 4–6 weeks to run tooling-only while the store and product page are built, then turn on paid ads once there's something worth sending traffic to.

> A Meta ad account with no spend history can technically launch same-day, but Meta increasingly requires business verification for higher spending limits and faster appeals — start that verification in Phase 1, not Phase 4, since it can take days to clear.

### 3.3 Suggested month-by-month allocation

| Month | Tooling | Ad spend | Total | Focus |
|---|---|---|---|---|
| 1 | ~$45 | $0 | ~$45 | Build agents, research niche, set up store (no ads yet) |
| 2 | ~$50 | ~$100–130 | ~$150–180 | Launch store, first Meta campaigns at $5–10/day, approval workflow live |
| 3+ | ~$50–60 | ~$140–150 | ~$190–200 | Iterate on winning ads, kill losers, consider Shopify annual billing |

---

## 4. Business Model & Niche Strategy

You asked the AI to choose the niche and business model rather than specifying one. This section defines the methodology the Researcher agent follows so that choice is systematic — and gives you a clear rubric to sanity-check its recommendation against.

### 4.1 Business model decision framework

| Model | Upfront capital | Margin | Speed to launch | Best when… |
|---|---|---|---|---|
| Dropshipping | Lowest ($0–$200) | 10–30% | Fastest (days) | Validating demand fast on a tight budget; fine with supplier/shipping variability. |
| Print-on-demand | Low ($0–$100) | 20–40% | Fast (days) | The niche is design/identity-driven (fandoms, hobbies, niche humor) rather than a specific physical product spec. |
| Private label | Highest ($500–$5,000+) | 40–65% | Slow (weeks–months) | A validated winning product already exists and you're ready to invest in owning margin and brand — not a Phase 1–4 fit given the budget. |

**Recommendation given your $200/month budget:** start with dropshipping or print-on-demand — both keep capital risk near zero while the AI validates demand. The Researcher agent should default to whichever scores higher for the chosen niche using the rubric below, and only propose private label as a "phase 2, once profitable" graduation path.

### 4.2 Niche & product research methodology (Researcher agent)

Every niche/product candidate the AI surfaces gets scored 1–10 across the factors below, stored in the `products` table. Only candidates scoring 7+ overall are presented to you for approval to move into store setup.

- **Demand signal (0–2):** search trend trajectory, TikTok/Meta ad library saturation — rising or stable beats declining.
- **Problem clarity (0–2):** does it solve one specific, describable pain point? Vague/lifestyle products score lower.
- **Competitive gap (0–2):** are existing sellers weak on price, positioning, or creative — not just "is it competitive."
- **Margin viability (0–2):** realistic landed cost vs. sellable price leaves at least 2.5–3x markup room after ads and fees.
- **Shippability/return risk (0–2):** lightweight, not fragile, low return-rate category (avoid apparel-sizing-dependent or easily-broken items for v1).

Competitor and brand snapshots (already modeled in the schema) get pulled for the top 3–5 candidates before you approve a final niche — you'll see who else sells it, at what price, and where they're weak.

---

## 5. Technical Architecture

> **Status note (2026-07-21):** this section is the *original* technical recommendation from when this plan was written. A separate, code-level security/reliability review (`CLAUDE_CODE_BUILD_PLAN.md`) was done immediately after, and its recommendations were what actually got built — deliberately overriding a few of the choices below. The as-built reality is summarized after each subsection; treat `CLAUDE_CODE_BUILD_PLAN.md` and the repo itself as authoritative on technical specifics, and this section as historical context for why those decisions were revisited. Sections 1-4 and 6-10 (budget, niche strategy, compliance, KPIs, replication) are unaffected by any of this and remain the live reference.

This keeps the existing repo's structure — it's sound — and resolves the open decisions: which LLM powers the agents, how approval gating actually works in code, and how the CLI tool (`assistant.py`) relates to the `backend/` system (they currently overlap).

### 5.1 Resolving the duplication: assistant.py vs backend/

The repo currently has two parallel systems: a simple CLI advisor (`assistant.py`, OpenAI-direct, single-turn Q&A) and a fuller `backend/` scaffold (FastAPI + CrewAI agents + Supabase + Telegram, mostly stubbed). Recommendation: retire `assistant.py` as the long-term interface once `backend/` is live — keep it only as a lightweight local testing tool for prompting ideas before they're wired into an agent. All real store operations should run through `backend/`, not the CLI.

**As built:** `assistant.py` and the other root-level v1 prototype files (`modules/`, `utils/`, `data/`) were deleted outright in Phase 0, rather than kept as a local testing tool — they were superseded stubs not used by `backend/`, and keeping them around risked someone (human or AI) mistaking them for the real system.

### 5.2 Agent brain

**Recommended:** Claude Haiku 4.5 via the Anthropic API directly, replacing OpenRouter + Hermes-3 as the default. Reasoning: comparable cost (~$1 input / $5 output per million tokens), and more reliable structured tool-calling — which matters once agents are actually taking actions (creating listings, drafting ad campaigns) rather than just answering questions. Keep OpenRouter as a fallback/config option — don't hard-code a single provider.

**As built:** OpenRouter was kept as the *only* gateway, not replaced with a direct Anthropic SDK integration — one API key reaches every model needed (Claude and otherwise) without a separate Anthropic account/SDK, and switching models is a config string change, not a code change. Model tiering ended up more granular than a single default: `OPENROUTER_MODEL`/`OPENROUTER_FAST_MODEL` (Claude Haiku 4.5, general/extraction), `OPENROUTER_RESEARCH_MODEL` (Claude Sonnet 5, research synthesis only — a deliberate cost/quality tradeoff scoped to just that one task), `OPENROUTER_FALLBACK_MODEL` (GPT-5.6 Luna, for real redundancy against an Anthropic-specific outage).

### 5.3 Stack (unchanged from repo, confirmed as right-sized)

| Layer | Technology | Status |
|---|---|---|
| Agent brain | Claude Haiku 4.5 / Sonnet 5 via **OpenRouter** | As built — see 5.2's note |
| Agent framework | CrewAI | As planned |
| Backend | FastAPI on VPS (PM2) | As planned |
| Database | Supabase (Postgres) | As built — see 5.4's note; schema differs from the original draft below |
| Frontend | HTML/CSS/JS on Vercel | As planned |
| Approval channel | Telegram Bot | As planned — the primary approval UI, not just notifications |
| Store | Shopify **GraphQL** Admin API | As built — REST was migrated off (deprecated for products/variants since 2024-04); custom-app static token, no OAuth (see 5.5) |
| Ads | Meta Marketing API | Not yet built — Phase 5. TikTok deferred (Section 3.2) |
| Email | Gmail API | Not yet built — Phase 5, unchanged |
| Search | **Tavily** | As built, replacing Serper (free tier) |

### 5.4 Approval gate — concrete implementation

Add an `autonomy_tier` field (0/1/2, matching Section 2.1) to config, and an `approval_required` check computed per action type. Every tool call that would spend money or publish publicly (`create_meta_campaign`, publish product listing, send customer email at scale) checks this before executing:

- **Tier 0:** every such call writes to `agent_tasks` with status `"pending_approval"` and pings Telegram with an inline Approve/Reject keyboard. The tool does not execute until a corresponding approval record is written.
- **Tier 1:** the same check runs, but auto-approves if the action is within the configured per-action cap (e.g. `daily_budget <= AUTO_APPROVE_AD_CAP`); otherwise falls back to Tier 0 behavior.
- **Tier 2:** check is skipped; action executes immediately and is logged.

This means the tier is a single config value — moving from Tier 0 to Tier 1 later doesn't touch agent logic, only the gate.

**As built:** there's no `autonomy_tier` config flag or Tier 1/2 mechanism — only Tier 0 (approve everything) exists, hardcoded, which matches "stay here for at least the first 30 days" from Section 2.1 anyway. The schema is `actions` (proposed action + status) / `approvals` (the decision) / `audit_log` (append-only lifecycle trail) / `jobs` (durable background-task queue) — not `agent_tasks`/`decisions` as originally sketched; the build-plan review judged the original broader schema (`stores`, `store_policies`, `model_calls`, `evidence`, `experiments`, etc.) right-shaped for running many stores with a team, not a single operator validating one store, and trimmed to the four tables that actually gate risk. `record_approval()` uses a conditional database update (not a raw insert) so two near-simultaneous decisions on the same action can't both execute. Building the Tier 1/2 switch is a real future option, not abandoned — just not needed yet at Tier 0.

### 5.5 Shopify connection

**As built (not in the original plan):** this is a single self-owned store, not an app installed on other merchants' stores, so it connects via a custom app's static Admin API access token (generated once in Shopify admin) rather than a full OAuth install flow — OAuth's authorization-code-grant machinery (callback endpoint, `state`/HMAC verification, shop-domain allowlist) solves a problem this project doesn't have. This still holds under the Section 9 replication plan, since each future store gets its own instance and its own token, not one app dynamically installing across many stores. Shopify webhooks (HMAC-verified) push real-time order/inventory alerts to Telegram instead of polling on a cron.

---

## 6. Platform Compliance & Legal Basics

### 6.1 Ad platform rules that directly affect an AI-run store

- Meta requires an "AI-generated" label on ad creative where AI substantially generated or modified the visual/audio (AI product images, synthetic voiceovers, AI video). Build this labeling into the ad-creation tool now — don't bolt it on later.
- Meta's own guidance is that full end-to-end AI automation without human review of creative is exactly the pattern that gets flagged — another point in favor of the Tier 0 approval gate, independent of your own risk preference.
- Business verification in Meta Business Settings unlocks higher spend limits and faster appeals — start this in Phase 1, it can take days.

### 6.2 Business & tax basics (US, general information — not legal or tax advice)

- You do not need an LLC to start selling on Shopify — sole proprietorship is legal, but offers no liability separation between you and the business. Many sellers form an LLC once revenue is consistent, not before launch.
- Shopify is not a marketplace facilitator — you (not Shopify) are responsible for collecting and remitting sales tax in states where you have nexus. You automatically have nexus in your home state; economic nexus elsewhere typically triggers at $100,000 in sales or 200 transactions/year in that state.
- Register for a sales tax permit in your home state before your first sale; Shopify's tax settings can calculate but won't register or file on your behalf.

> This section is general information, not legal or tax advice — confirm your specific obligations with an accountant once the store has real revenue, particularly before expanding to new states or forming an entity.

---

## 7. Phased Roadmap

> **Note:** these are business milestones, numbered independently from `ROADMAP.md`/`CLAUDE_CODE_BUILD_PLAN.md`'s Phase 0-5 (the technical build order actually executed — security hardening, approval gate, reliability, Shopify GraphQL, webhooks, then marketing). Don't read "Phase 3" here as the same thing as "Phase 3" there. Status column added 2026-07-21.

Each milestone ends with a clear "you get" outcome and an explicit approval checkpoint.

| Milestone | Goal | Key additions vs. original roadmap | Approval checkpoint | Status |
|---|---|---|---|---|
| 1 — Foundation | Agents, Telegram, dashboard, Supabase all connected and running | Approval gate built in from the start; start Meta business verification | You approve the first end-to-end test task (a dummy research request) to confirm the approval loop works | ✅ Done (technical Phases 0-2) |
| 2 — Research Intelligence | AI researches and scores niches/products autonomously | Apply the 5-factor scoring rubric (Section 4.2); only 7+ scored candidates surface to you | You approve the final niche + business model before store setup begins | Research pipeline is live; no niche formally approved yet |
| 3 — Shopify Integration | AI builds and manages the actual store | Store stays unpublished/password-protected until you approve going live | You approve the store going public | ✅ Connected (technical Phase 3-4); store not yet public |
| 4 — Marketing Automation | AI writes and runs ad campaigns | Meta only (TikTok deferred); every campaign launch and AI-generated creative asset requires approval and carries the AI-disclosure label | You approve each new campaign and each budget change | 🔜 Not started (technical Phase 5) |
| 5 — Customer Operations | AI drafts/handles support and reviews | Auto-send only for a pre-approved allowlist of routine replies (order status, shipping ETA); everything else drafted for approval | You approve the initial allowlist of auto-sendable reply templates | 🔜 Not started (technical Phase 5) — needs Gmail OAuth + Judge.me |
| 6 — Full Intelligence & Replication | Daily/weekly reporting, anomaly detection, packaging this as a reusable framework | Add a "new store" bootstrap script that clones the agent config + schema for a second store once this one is profitable | You approve moving any store from Tier 0 to Tier 1 autonomy | Not started |

---

## 8. KPIs & Kill Criteria

An AI-run store still needs the same discipline any store needs: clear numbers that decide whether to keep going, adjust, or stop. The Analyst agent should report these weekly.

### 8.1 Track weekly

- Ad spend, revenue, and ROAS (target: sustained 2.0x+ ROAS before scaling spend up)
- Conversion rate on the store (benchmark: 1.5–3% for cold traffic dropshipping/POD)
- Contribution margin per order after product cost, shipping, and ad spend
- Refund/return rate (flag anything above 10–15%, category-dependent)
- Number of AI decisions approved vs. rejected — tracks readiness to move autonomy tiers

### 8.2 Kill / pivot criteria

- If a product hasn't reached breakeven ROAS after $150–200 of cumulative ad spend, kill it and let the Researcher agent propose the next candidate — don't keep feeding a loser.
- If 3 consecutive AI-proposed products fail to reach breakeven, pause and review the scoring rubric itself (Section 4.2) rather than continuing to spend testing products.

---

## 9. Replication Framework — Turning This Into a Multi-Store Workflow

Since the goal beyond store #1 is a repeatable framework, build for this from Phase 1 rather than retrofitting it later:

- Keep all niche-specific data (products, competitors, brand voice) in Supabase rows, never hard-coded in agent prompts or tool code — agent code should be niche-agnostic from day one.
- Store-specific config (Shopify credentials, ad account IDs, brand name/voice) lives in one config block per store, not scattered across files — this is what a "new store" bootstrap script duplicates.
- The scoring rubric, approval-gate logic, and agent roles are the reusable IP; the niche and creative are what changes per store.
- Once store #1 clears Tier 1 autonomy for a full quarter (Section 2.1), Phase 6's bootstrap script becomes the template for store #2 — same agents, same approval gate, new Supabase project and Shopify store.

---

## 10. Immediate Next Steps

1. Confirm the model switch to Claude Haiku 4.5 (or say if you'd rather keep OpenRouter/Hermes-3) — this affects Section 5.2 and the `.env` template.
2. Get the four Phase 1 keys: Anthropic (or OpenRouter) API key, Telegram bot token, Supabase project, Serper API key — `docs/SETUP.md` already has the steps.
3. Start Meta Business verification now (Section 6.1) — it runs in parallel and can take days.
4. I'll build out the Tier 0 approval-gate code in `backend/` (Section 5.4) so the first end-to-end test — a dummy research request you approve via Telegram — is possible as soon as the keys are in.

---

## Appendix — Sources

Pricing and policy figures cited in Sections 3 and 6 were retrieved via web search on July 20, 2026:

- Shopify pricing 2026 — shopify.com/pricing and aggregator sources
- Meta Ads minimum daily budgets and business verification — Meta Transparency Center, stackmatix.com
- TikTok Ads minimum budgets — ads.tiktok.com/help, stackmatix.com
- Supabase pricing 2026 — supabase.com pricing and aggregator sources
- LLM API pricing 2026 (Claude Haiku 4.5, GPT, DeepSeek comparisons) — multiple pricing-tracker sites, cross-checked
- US dropshipping tax/LLC basics — shopify.com/blog tax and business-license guides

*Re-verify all figures before committing spend — platform pricing and ad policy change frequently.*
