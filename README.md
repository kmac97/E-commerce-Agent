# 🤖 E-commerce AI Agent

A fully autonomous AI agent system that researches products, manages your Shopify store, runs ads, handles customer support, monitors reviews, and manages emails — all from your phone.

---

## What This Does

You tell the agent what you want. It goes and does it.

- **Phone (Telegram)** — send commands, get updates, approve decisions
- **Web Dashboard** — full view of everything the agents are doing
- **Autonomous agents** — research, list products, manage ads, reply to customers

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Agent brain | Hermes 3 via OpenRouter | Plans, reasons, uses tools |
| Agent framework | CrewAI | Manages multiple agents working together |
| Backend | FastAPI (Python) | API server, runs on your Hostinger VPS |
| Database | Supabase | Stores everything, realtime updates, auth |
| Frontend | HTML/CSS/JS | Web dashboard, deployed to Vercel |
| Mobile | Telegram Bot | Commands and notifications on your phone |
| Store | Shopify API | Product listings, orders, inventory |
| Ads | Meta + TikTok APIs | Campaign management |
| Email | Gmail API | Customer emails, supplier outreach |
| Reviews | Shopify + Judge.me | Monitor and respond to reviews |
| Search | Serper API | Live web research for agents |

---

## Architecture

```
Your Phone
├── Telegram  →  commands, alerts, approvals
└── Browser   →  web dashboard (Vercel)
        ↓
  Hostinger VPS
  ├── FastAPI (API server)
  ├── Telegram Bot
  └── CrewAI Agents
      ├── Researcher Agent
      ├── Store Manager Agent
      ├── Marketing Agent
      ├── Support Agent
      └── Analyst Agent
        ↓
  Supabase (database, auth, realtime)
        ↓
  External APIs
  ├── OpenRouter → Hermes 3
  ├── Shopify API
  ├── Meta Ads API
  ├── Gmail API
  └── Serper (web search)
```

---

## Project Structure

```
ecommerce-agent/
├── backend/                    # Runs on Hostinger VPS
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # All settings
│   ├── requirements.txt
│   ├── .env                    # Your secrets (never share)
│   │
│   ├── agents/                 # CrewAI agents
│   │   ├── crew.py             # Orchestrator — runs the crew
│   │   ├── researcher.py       # Product & niche research
│   │   ├── store_manager.py    # Shopify management
│   │   ├── marketer.py         # Ads and marketing
│   │   ├── support_agent.py    # Customer support
│   │   └── analyst.py          # Performance analysis
│   │
│   ├── tools/                  # What agents can do
│   │   ├── shopify_tools.py    # Shopify API actions
│   │   ├── search_tools.py     # Web search
│   │   ├── email_tools.py      # Email management
│   │   ├── ads_tools.py        # Meta/TikTok ads
│   │   └── review_tools.py     # Review management
│   │
│   ├── telegram/               # Telegram bot
│   │   ├── bot.py              # Bot setup
│   │   └── commands.py         # Command handlers
│   │
│   ├── api/                    # FastAPI routes
│   │   ├── agents.py           # Trigger agents
│   │   ├── research.py         # Research endpoints
│   │   └── dashboard.py        # Dashboard data
│   │
│   └── database/               # Supabase
│       ├── client.py           # Supabase connection
│       └── models.py           # Data schemas
│
├── frontend/                   # Deploys to Vercel
│   ├── index.html              # Dashboard
│   ├── style.css               # Styling
│   ├── app.js                  # Dashboard logic
│   └── vercel.json             # Vercel config
│
└── docs/
    ├── README.md               # This file
    ├── ROADMAP.md              # Build phases
    └── SETUP.md                # Step-by-step setup guide
```

---

## Setup Overview

Full step-by-step instructions are in `docs/SETUP.md`.

### What you'll need:
- [ ] OpenRouter API key (openrouter.ai)
- [ ] Telegram Bot token (from @BotFather on Telegram)
- [ ] Supabase project (supabase.com — free)
- [ ] Hostinger VPS with Python 3.10+ installed
- [ ] Vercel account (vercel.com — free)
- [ ] Serper API key for web search (serper.dev — free tier)
- [ ] Shopify store + API credentials (when ready)
- [ ] Meta Business account (for ads — Phase 4)
- [ ] Gmail API credentials (Phase 5)

### Quick start:
```bash
# On your Hostinger VPS
git clone <your-repo>
cd ecommerce-agent/backend
pip install -r requirements.txt
cp .env.example .env
# Fill in your .env file
python main.py
```

---

## API Keys — Cost Guide

| Service | Free Tier | Cost When Paid |
|---------|-----------|---------------|
| OpenRouter | Yes (limited) | Pay per token, very cheap |
| Hermes 3 70B | Via OpenRouter | ~$0.001–0.003/query |
| Serper (search) | 2,500 free searches | $50/month after |
| Supabase | 500MB, 2 projects | $25/month |
| Telegram Bot | Always free | Free |
| Vercel | Always free (hobby) | Free |
| Shopify | 3-day trial | $29–$79/month |

---

## Phases

See `ROADMAP.md` for the full build plan.
