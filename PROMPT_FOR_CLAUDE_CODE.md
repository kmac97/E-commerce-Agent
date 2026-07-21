You're working in the `E-commerce Assistant` repo — an AI-run e-commerce store project (FastAPI backend, CrewAI agents, Supabase, a Telegram bot called "Max", and a dashboard PWA). It is **live and deployed**: a real Shopify store is connected (`sp0t1s-41.myshopify.com`), the backend runs on a Hostinger VPS under PM2 and is reachable at `e-comagent.duckdns.org`, and the Telegram bot is active. Treat this as production, not a greenfield project — every change should assume real data and a real store are on the other end.

Two AI code reviews have already been done on this repo (one by me, one by GPT, cross-checked against each other) and the findings are written up in **`CLAUDE_CODE_BUILD_PLAN.md`** in this repo's root. Read that file in full before doing anything else — it has the verified findings, the phased plan, and specific reasoning for what to prioritize and what to defer. `AI_Store_Master_Plan.md` has the underlying business/budget plan (sub-$200/month, Meta-only ads, approve-everything-first operating model) if you need that context too.

## Ground rules for this whole engagement

1. **Work one phase at a time, in the order the build plan lays out.** Don't jump ahead to features or cleanup in later phases while Phase 0 items are still open — the plan explains why (nothing else matters if the API is wide open).
2. **Some steps require me to take action outside this repo** (rotating the Shopify access token in the Shopify admin, restarting the PM2 process on the VPS, updating `.env` on the server, DNS/deploy steps). You don't have access to those systems. When you hit one of these, stop, tell me exactly what to do and why, and wait for me to confirm it's done before continuing anything that depends on it.
3. **Before writing code for a phase, give me a short plan for that phase** (files touched, what changes, how you'll verify it) and let me sanity-check it — especially for Phase 0's auth/SSRF/Telegram changes, since a mistake there could lock me out of my own bot or dashboard instead of just attackers.
4. **Commit incrementally**, one logical change per commit, with clear messages. Don't bundle unrelated fixes into one commit.
5. **Write or update tests where it's cheap to do so** (the auth checks, the SSRF allow/deny logic, the Telegram owner filter are all good candidates for quick unit tests), but don't block on building a full test suite — this is a solo project, not enterprise software.
6. **Flag anything in the build plan you disagree with or think is wrong once you're actually in the code** — it was written from reading the source, not from running it, so it may have missed something a live run or deeper look surfaces.
7. **After each phase, give me a short summary**: what changed, what I need to verify manually (e.g. "send `/start` to the bot from a second Telegram account and confirm it's ignored"), and what's next.

## Where to start

1. Read `CLAUDE_CODE_BUILD_PLAN.md` end to end.
2. Read the actual files it references (`backend/main.py`, `backend/api/shopify_auth.py`, `backend/tgbot/bot.py` and `commands.py`, `backend/api/agents.py`, `backend/tools/search_tools.py`, `frontend/app.js`) so you're working from the current real code, not just the plan's summary of it.
3. Start Phase 0, item 1: the exposed Shopify OAuth route. Tell me what to do in the Shopify admin (rotate the token) and confirm with me before you touch `shopify_auth.py`, since disabling that route and rotating the token need to happen together.
4. Work through the rest of Phase 0 in order: API auth, CORS, rate limiting, Telegram owner-restriction, SSRF fixes on the two import/spy endpoints, frontend sanitization, the two dead-code bugs (`search_tools.py`'s missing config var, the missing logger in `api/agents.py`), reconciling the model config disagreement, and deleting the superseded root-level prototype (`assistant.py`, `modules/`, `utils/`, `data/`).
5. Don't start Phase 1 (the approval-gate tables and durable job queue) until Phase 0 is fully done and I've confirmed the manual steps (token rotation, any VPS restart) are complete.

Once Phase 0 is done and verified, ask me whether to proceed straight into Phase 1 or whether priorities have changed.
