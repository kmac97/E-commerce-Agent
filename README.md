# 🤖 E-commerce AI Agent

An AI-assisted e-commerce operations system: agents research products and niches, manage your Shopify store, and monitor orders/inventory — everything that spends money or writes to your store goes through a Telegram Approve/Reject step first. You're the approver, not the operator.

> **Planning docs:** [`CLAUDE_CODE_BUILD_PLAN.md`](CLAUDE_CODE_BUILD_PLAN.md) is the technical/security build plan (the phase numbers below match it). [`AI_Store_Master_Plan.md`](AI_Store_Master_Plan.md) is the business plan — budget, niche-scoring methodology, compliance basics, and the Phase 5 marketing rollout.

---

## What This Does

You tell the agent what you want researched or checked. It goes and does the work — and anything that would create a listing, edit a live product, or spend money waits for your approval on Telegram first.

- **Phone (Telegram)** — send commands, get real-time alerts (new orders, low stock), approve or reject proposed actions
- **Web Dashboard** — product research pipeline, task history, revenue charts
- **Agents** — product/niche research, store monitoring, price suggestions — propose, never write directly

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Agent brain | Claude Haiku 4.5 via OpenRouter (default/extraction), Claude Sonnet 5 (research synthesis), GPT-5.6 Luna (fallback) | Plans, reasons, uses tools |
| Agent framework | CrewAI | Manages multiple agents working together |
| Backend | FastAPI (Python) | API server, runs on a Hostinger VPS under PM2 |
| Database | Supabase (Postgres) | Products, research, durable jobs, approval-gate audit trail |
| Frontend | HTML/CSS/JS (PWA) | Web dashboard, deployed to Vercel |
| Mobile | Telegram Bot | Commands, real-time alerts, Approve/Reject buttons |
| Store | Shopify GraphQL Admin API | Product listings, orders, inventory — plus real-time webhooks |
| Search | Tavily | Live web research for the research agent |
| Ads | Meta Ads API | Not yet built — Phase 5 (TikTok deferred, see master plan) |
| Email / Reviews | Gmail API / Judge.me | Not yet built — Phase 5 |

---

## Architecture

```
Your Phone
├── Telegram  →  commands, real-time alerts, Approve/Reject
└── Browser   →  web dashboard (Vercel)
        ↓
  Hostinger VPS (PM2)
  ├── FastAPI (API server, X-Api-Key auth, rate-limited)
  ├── Telegram Bot
  ├── Durable job worker (Supabase-backed queue)
  └── CrewAI Agents
      ├── Researcher Agent
      ├── Store Manager Agent (read-only Shopify tools)
      ├── Marketer / Support / Analyst Agents (stubs — Phase 5)
        ↓
  Supabase (products, research, actions/approvals/audit_log, jobs)
        ↓
  External APIs
  ├── OpenRouter → Claude Haiku 4.5 / Sonnet 5 / GPT-5.6 Luna fallback
  ├── Shopify GraphQL Admin API (+ orders/inventory webhooks)
  ├── Tavily (web search)
  └── Meta Ads / Gmail / Judge.me (Phase 5, not yet connected)
```

Every Shopify write (create a draft, edit a listing) goes: **agent or dashroom action → proposed `actions` row → Telegram Approve/Reject → execution**. Nothing writes to Shopify directly.

---

## Project Structure

```
ecommerce-agent/
├── backend/                       # Runs on Hostinger VPS
│   ├── main.py                    # FastAPI entry point, startup/shutdown lifecycle
│   ├── config.py                  # All settings
│   ├── requirements.txt           # Direct dependencies, pinned
│   ├── requirements-lock.txt      # Full pinned dependency tree (from production)
│   ├── .env                       # Your secrets (never share)
│   │
│   ├── agents/                    # CrewAI agents + orchestration
│   │   ├── crew.py                # Orchestrator — proposes Shopify drafts from research
│   │   ├── researcher.py          # Product & niche research
│   │   ├── store_manager.py       # Shopify agent (read-only tools only)
│   │   ├── marketer.py / support_agent.py / analyst.py   # Stubs — Phase 5
│   │   ├── trending.py            # Trending-product detection
│   │   └── job_worker.py          # Durable job queue polling loop
│   │
│   ├── tools/                     # What agents/routes can do
│   │   ├── shopify_tools.py       # Shopify GraphQL Admin API
│   │   ├── llm_client.py          # Shared LLM call helper (retry/backoff/fallback)
│   │   ├── safe_fetch.py          # SSRF-safe URL fetching
│   │   ├── email_tools.py / review_tools.py / ads_tools.py   # Stubs — Phase 5
│   │
│   ├── tgbot/                      # Telegram bot
│   │   ├── bot.py                 # Bot setup, startup/shutdown
│   │   ├── commands.py            # Command handlers + Max (chat assistant)
│   │   ├── approvals.py           # Approve/Reject callback handling
│   │   ├── store_monitor.py       # Price-suggestion cron + manual /inventory check
│   │   └── briefing.py            # Daily briefing
│   │
│   ├── api/                       # FastAPI routes
│   │   ├── agents.py              # Trigger agents, dashboard chat
│   │   ├── research.py            # Research endpoints
│   │   ├── dashboard.py           # Dashboard data + Shopify-draft proposal endpoint
│   │   ├── webhooks.py            # Shopify order/inventory webhooks (HMAC-verified)
│   │   ├── auth.py                # X-Api-Key dependency
│   │   └── rate_limit.py          # Shared slowapi limiter
│   │
│   └── database/
│       ├── client.py              # Async Supabase client + all DB helpers
│       ├── models.py               # Pydantic models
│       └── migrations/            # SQL migrations (actions/approvals/audit_log/jobs + constraints)
│
├── frontend/                       # Deploys to Vercel
│   ├── index.html / style.css / app.js
│   └── vercel.json
│
├── CLAUDE_CODE_BUILD_PLAN.md        # Technical/security build plan (phase numbers below)
├── AI_Store_Master_Plan.md          # Business plan (budget, niche scoring, Phase 5)
└── docs/
    ├── README.md
    ├── ROADMAP.md
    └── SETUP.md
```

---

## Setup Overview

Full step-by-step instructions are in `docs/SETUP.md`.

### What you'll need:
- [ ] OpenRouter API key (openrouter.ai) — covers Claude + fallback models through one key
- [ ] Tavily API key (tavily.com — free tier) for research
- [ ] Telegram Bot token (from @BotFather on Telegram)
- [ ] Supabase project (supabase.com — free)
- [ ] Hostinger VPS (or similar) with Python 3.11+ installed
- [ ] Vercel account (vercel.com — free) for the dashboard
- [ ] A dashboard API key you generate yourself (`openssl rand -hex 32`)
- [ ] Shopify store + a custom app's Admin API access token + webhook secret (when ready)
- [ ] Meta Business account, Gmail API credentials, Judge.me — Phase 5, not yet needed

### Quick start:
```bash
# On your VPS
git clone <your-repo>
cd ecommerce-agent/backend
pip install -r requirements-lock.txt   # exact versions matching production
cp .env.example .env
# Fill in your .env file
python main.py
```

---

## API Keys — Cost Guide

| Service | Free Tier | Cost When Paid |
|---------|-----------|---------------|
| OpenRouter | Yes (limited) | Pay per token — Haiku 4.5 ~$1/$5 per million tokens in/out, Sonnet 5 more, used sparingly for research only |
| Tavily (search) | 2,500 free searches/month | Paid tiers beyond that |
| Supabase | 500MB, 2 projects | $25/month once you outgrow the free tier |
| Telegram Bot | Always free | Free |
| Vercel | Always free (hobby) | Free |
| Shopify | 3-day trial | $29/mo (annual) – $39/mo (monthly) |
| VPS (Hostinger or similar) | — | $5–$10/month |

Full budget breakdown and month-by-month plan: see `AI_Store_Master_Plan.md`, Section 3.

---

## Current Status

Phases 0–4 of the technical build plan are complete and deployed: API auth/CORS/rate-limiting, the Telegram Approve/Reject approval gate with a durable job queue, an async Supabase client, pinned dependencies, Shopify's GraphQL Admin API, and real-time order/inventory webhooks. Phase 5 (Meta Ads, plus the deferred email/review support tooling) hasn't started. See `ROADMAP.md` for the full phase-by-phase breakdown.
