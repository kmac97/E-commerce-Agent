# 🔧 Setup Guide

Step-by-step instructions to get the E-commerce AI Agent running from scratch.

---

## Step 1 — Get Your API Keys

Do this first. Collect all keys before touching any code.

### OpenRouter (AI model access)
One key covers every model this project uses (Claude Haiku 4.5 default, Claude Sonnet 5 for research synthesis, GPT-5.6 Luna as fallback) — no separate Anthropic/OpenAI keys needed.
1. Go to [openrouter.ai](https://openrouter.ai)
2. Sign up → Dashboard → API Keys → Create Key
3. Add a small amount of credit ($5 is plenty to start)
4. Copy the key — starts with `sk-or-`

### Telegram Bot
1. Open Telegram on your phone
2. Search for `@BotFather`
3. Send `/newbot`
4. Follow prompts — give it a name and username
5. Copy the token it gives you (looks like `123456789:ABCdef...`)
6. To get your personal Chat ID: search `@userinfobot` on Telegram and send `/start`

### Supabase
1. Go to [supabase.com](https://supabase.com) and sign in
2. New Project → give it a name → set a database password (save it)
3. Go to Settings → API
4. Copy: Project URL and `anon/public` key

### Tavily (web search for the research agent)
1. Go to [tavily.com](https://tavily.com)
2. Sign up → API Key
3. Free tier gives 2,500 searches/month

(Serper is legacy/unused — Tavily replaced it. `backend/.env.example` still lists a `SERPER_API_KEY` slot in case you want to wire it back in as a fallback provider later, but it's not required.)

---

## Step 2 — Set Up Supabase Tables

Go to your Supabase project → SQL Editor → paste and run this:

```sql
-- Research saved by agents
CREATE TABLE research (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  type TEXT NOT NULL,  -- 'product', 'niche', 'competitor', 'brand'
  topic TEXT NOT NULL,
  score INTEGER,       -- 1-10 if applicable
  data JSONB NOT NULL,
  notes TEXT
);

-- Agent task log
CREATE TABLE agent_tasks (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  agent TEXT NOT NULL,        -- 'researcher', 'store_manager', etc.
  task TEXT NOT NULL,
  status TEXT DEFAULT 'pending',  -- pending, running, complete, failed
  input JSONB,
  output JSONB,
  error TEXT,
  duration_seconds INTEGER
);

-- Saved product ideas
CREATE TABLE products (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  name TEXT NOT NULL,
  niche TEXT,
  score INTEGER,
  cost_estimate DECIMAL,
  sell_price_estimate DECIMAL,
  margin_estimate DECIMAL,
  status TEXT DEFAULT 'idea',  -- idea, researching, testing, active, dropped
  notes TEXT,
  data JSONB
);

-- Competitor notes
CREATE TABLE competitors (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  name TEXT NOT NULL,
  url TEXT,
  niche TEXT,
  strengths TEXT,
  weaknesses TEXT,
  pricing JSONB,
  data JSONB
);

-- Agent memory (for pgvector later)
CREATE TABLE memories (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  agent TEXT,
  content TEXT NOT NULL,
  metadata JSONB
);

-- Supabase's SQL editor auto-enables Row Level Security on new tables with
-- no policies, which silently blocks every insert/update since this app has
-- no per-user auth context (one backend, one shared service key). Disable it
-- to match the rest of the schema below.
ALTER TABLE research DISABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tasks DISABLE ROW LEVEL SECURITY;
ALTER TABLE products DISABLE ROW LEVEL SECURITY;
ALTER TABLE competitors DISABLE ROW LEVEL SECURITY;
ALTER TABLE memories DISABLE ROW LEVEL SECURITY;
```

Then run the three migrations in `backend/database/migrations/` **in order** (001, 002, 003) — same SQL Editor, one at a time. These add the `actions`/`approvals`/`audit_log` approval-gate tables, the `jobs` durable queue table, and the DB-level constraints backing the approval gate's race protection. Each file has its own RLS-disable statements and comments explaining what it does.

---

## Step 3 — Configure Your VPS (Hostinger)

SSH into your Hostinger VPS:

```bash
ssh root@your-vps-ip
```

Install Python and dependencies:

```bash
apt update && apt upgrade -y
apt install python3.11 python3-pip python3.11-venv git -y
```

Clone your project:

```bash
git clone <your-repo-url>
cd ecommerce-agent/backend
```

Create a virtual environment:

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Set up your environment file:

```bash
cp .env.example .env
nano .env   # Fill in all your keys
```

---

## Step 4 — Fill In Your .env File

`backend/.env.example` has the full, current template with comments — copy it to `.env` and fill it in. The shape of it:

```env
# API auth -- the dashboard sends this back as X-Api-Key. Generate with: openssl rand -hex 32
API_KEY=

# CORS -- comma-separated origins allowed to call the API (your Vercel dashboard URL)
ALLOWED_ORIGINS=

# AI (via OpenRouter -- one key covers every model tier below)
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_MODEL=anthropic/claude-haiku-4.5
OPENROUTER_FAST_MODEL=anthropic/claude-haiku-4.5
OPENROUTER_FALLBACK_MODEL=openai/gpt-5.6-luna
OPENROUTER_RESEARCH_MODEL=anthropic/claude-sonnet-5

# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=your-personal-chat-id

# Supabase
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_KEY=your-anon-key

# Search
TAVILY_API_KEY=your-tavily-key

# Shopify (fill in when store is ready -- custom app token, not OAuth)
SHOPIFY_SHOP_URL=yourstore.myshopify.com
SHOPIFY_ACCESS_TOKEN=
SHOPIFY_WEBHOOK_SECRET=

# Meta Ads, Gmail (Phase 5 -- not needed yet)
META_APP_ID=
META_APP_SECRET=
META_ACCESS_TOKEN=
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
```

---

## Step 5 — Run the Backend

```bash
# Make sure you're in the backend folder with venv active
source venv/bin/activate
python main.py
```

You should see:
```
✅ Supabase connected
✅ Telegram bot started
✅ Job worker started
✅ FastAPI running on http://0.0.0.0:8000
✅ Model: anthropic/claude-haiku-4.5
```

---

## Step 6 — Deploy the Frontend to Vercel

The frontend is plain HTML/CSS/JS (no build step) — Vercel just serves it as a static site.

1. Push your project to GitHub
2. Go to [vercel.com](https://vercel.com) → New Project → Import from GitHub
3. Set Root Directory to `frontend`
4. Deploy — no environment variables needed. `app.js` defaults `API_URL` to the production backend; override it by setting `window.API_URL` before `app.js` loads if you ever need to point a deployment at a different backend.

Your dashboard will be live at `https://your-project.vercel.app`

---

## Step 7 — Keep the Backend Running (VPS)

Install PM2 to keep the backend alive after you close the terminal:

```bash
apt install nodejs npm -y
npm install -g pm2
pm2 start "venv/bin/python3 main.py" --name ecommerce-agent
pm2 startup
pm2 save
```

**Important:** PM2 caches environment variables at process start. Any time you change `.env` (a new key, a rotated secret), restart with `pm2 restart ecommerce-agent --update-env` — a plain `pm2 restart` keeps running with the *old* cached values, which silently breaks anything relying on the new/changed variable while everything else keeps looking fine.

---

## Step 8 — Test It

Open Telegram and send your bot:
```
/start
```

You should get a welcome message. Then try:
```
/research posture correctors
```

The agent will go research posture correctors and send you back a full report.

---

## Troubleshooting

**Bot not responding:** Check `pm2 logs ecommerce-agent` on your VPS.

**Supabase errors:** Make sure you ran the SQL in Step 2 and your `.env` keys are correct.

**OpenRouter errors:** Check you have credit on your OpenRouter account.

**Dashboard prompts for an API key and rejects it (401s on every request):** the dashboard's key (stored in your browser's localStorage) has to match `API_KEY` in the VPS's `.env` exactly. If you changed `API_KEY` and restarted with a plain `pm2 restart` instead of `--update-env`, the running process may still have the *old* value cached — restart with `--update-env`, then re-enter the current key when the dashboard prompts for it.

**Dashboard not loading at all:** check `API_URL` at the top of `frontend/app.js` points to your actual backend URL, and that CORS's `ALLOWED_ORIGINS` in the backend `.env` includes your Vercel domain.
