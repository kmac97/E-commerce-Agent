# 🗺️ E-commerce AI Agent — Roadmap

This roadmap uses the same phase numbers as [`CLAUDE_CODE_BUILD_PLAN.md`](CLAUDE_CODE_BUILD_PLAN.md) (the technical/security plan this project has actually been built against). [`AI_Store_Master_Plan.md`](AI_Store_Master_Plan.md) has the business side — budget, niche-scoring methodology, compliance basics — most relevant once Phase 5 starts.

**Operating model:** every action that spends money or writes to Shopify goes through a Telegram Approve/Reject gate first. There's no autonomy-tier switch — that's the only mode right now, deliberately.

---

## ✅ Phase 0 — Security & Foundation
**Goal:** Lock the backend down before building anything else on top of it.

- [x] API key auth on every route, CORS restricted to real origins
- [x] Rate limiting on expensive/costed endpoints
- [x] Telegram bot restricted to the owner's chat ID only
- [x] SSRF protections on user-supplied-URL endpoints
- [x] Frontend XSS sanitization
- [x] Model config reconciled onto OpenRouter (no more per-file drift)
- [x] Legacy v1 prototype removed

**Got:** A backend that isn't wide open to anyone who finds the URL.

---

## ✅ Phase 1 — Approval Gate + Durable Jobs
**Goal:** Nothing spends money or writes to Shopify without a human tapping Approve.

- [x] `actions` / `approvals` / `audit_log` tables — full proposal → decision → execution trail
- [x] Telegram Approve/Reject buttons wired into every Shopify-write path
- [x] Durable job queue (`jobs` table + worker loop) — research tasks survive a process restart, not just `asyncio.create_task`
- [x] Idempotency keys prevent duplicate proposals for the same trigger

**Got:** A live system you can talk to from Telegram and see in your browser, with nothing able to spend money or publish without your approval.

---

## ✅ Phase 2 — Reliability Cleanup
**Goal:** Make the thing that's running actually robust.

- [x] Shared LLM call helper — retry/backoff, timeout, fallback model on provider outage
- [x] Async Supabase client throughout (no more blocking the event loop on every DB call)
- [x] Model tiering: Haiku 4.5 default, Sonnet 5 for research synthesis only, GPT-5.6 Luna as fallback
- [x] Pinned dependency versions + a full lock file

**Got:** A backend that degrades gracefully instead of silently breaking under load or a provider hiccup.

---

## ✅ Phase 3 — Shopify Integration
**Goal:** Talk to Shopify the way that isn't on a deprecation clock.

- [x] Migrated `shopify_tools.py` from REST (deprecated for products/variants since 2024-04) to the GraphQL Admin API
- [x] Custom-app static access token — no OAuth flow, since this is one self-owned store, not an app installed on other merchants' stores

**Got:** Product research → draft proposal → Telegram approval → real Shopify draft, all on a supported API.

---

## ✅ Phase 4 — Monitoring
**Goal:** Know what's happening in the store without polling for it.

- [x] Real-time Shopify webhooks (HMAC-verified) for new orders and low stock, replacing cron polling
- [x] Manual `/inventory`, `/orders`, `/prices` checks still available on demand

**Deferred to Phase 5:** wiring the Support agent to real email/review tools — `email_tools.py`/`review_tools.py` need Gmail OAuth and a Judge.me signup that don't exist yet, and there's no live customer/review activity to act on until the store has real traffic.

**Got:** A Telegram ping the moment an order comes in or stock gets low, instead of finding out on the next scheduled check.

---

## 🔜 Phase 5 — Marketing & Spend
**Goal:** The agent drafts and manages ad campaigns; you approve spend.

- [ ] Meta Ads API connected (primary/only ad channel — TikTok's ~$50/day platform minimum doesn't fit the budget, see master plan Section 3.2)
- [ ] Ad copy generator, AI-generated creative carries the required "AI-generated" disclosure label (Meta policy)
- [ ] Every campaign launch and budget change requires Telegram approval, hard spend caps enforced in code
- [ ] Support agent wired to real Gmail + Judge.me tools (deferred from Phase 4), draft-only, routed through the same approval gate

**Will get:** The agent drafts your ads and campaigns and drafts customer replies; you approve spend, creative, and sends before anything goes out.

---

## Timeline

| Phase | Status | Dependency |
|-------|--------|-----------|
| Phase 0 | ✅ Done | — |
| Phase 1 | ✅ Done | Supabase, Telegram bot |
| Phase 2 | ✅ Done | — |
| Phase 3 | ✅ Done | Shopify store live |
| Phase 4 | ✅ Done | Shopify webhooks registered |
| Phase 5 | 🔜 Not started | Meta Business verification, Gmail API credentials, Judge.me account |
