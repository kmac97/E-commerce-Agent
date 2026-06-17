# 🔧 Setup Guide

Step-by-step instructions to get the E-commerce AI Agent running from scratch.

---

## Step 1 — Get Your API Keys

Do this first. Collect all keys before touching any code.

### OpenRouter (AI model access)
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

### Serper (web search for agents)
1. Go to [serper.dev](https://serper.dev)
2. Sign up → API Key
3. Free tier gives 2,500 searches/month

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

-- Decisions log
CREATE TABLE decisions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  category TEXT,
  decision TEXT NOT NULL,
  reason TEXT,
  outcome TEXT
);

-- Agent memory (for pgvector later)
CREATE TABLE memories (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  agent TEXT,
  content TEXT NOT NULL,
  metadata JSONB
);
```

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

```env
# AI
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_MODEL=nousresearch/hermes-3-llama-3.1-70b

# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=your-personal-chat-id

# Supabase
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_KEY=your-anon-key

# Search
SERPER_API_KEY=your-serper-key

# Shopify (fill in when store is ready)
SHOPIFY_SHOP_URL=yourstore.myshopify.com
SHOPIFY_API_KEY=
SHOPIFY_API_SECRET=
SHOPIFY_ACCESS_TOKEN=

# Meta Ads (Phase 4)
META_APP_ID=
META_APP_SECRET=
META_ACCESS_TOKEN=

# Gmail (Phase 5)
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
✅ FastAPI running on http://0.0.0.0:8000
✅ Telegram bot connected
✅ Supabase connected
✅ OpenRouter connected — model: hermes-3-llama-3.1-70b
```

---

## Step 6 — Deploy the Frontend to Vercel

1. Push your project to GitHub
2. Go to [vercel.com](https://vercel.com) → New Project → Import from GitHub
3. Set Root Directory to `frontend`
4. Add environment variable: `VITE_API_URL` = `http://your-vps-ip:8000`
5. Deploy

Your dashboard will be live at `https://your-project.vercel.app`

---

## Step 7 — Keep the Backend Running (VPS)

Install PM2 to keep the backend alive after you close the terminal:

```bash
apt install nodejs npm -y
npm install -g pm2
pm2 start "python main.py" --name ecommerce-agent
pm2 startup
pm2 save
```

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

**Vercel dashboard not loading:** Check the `VITE_API_URL` environment variable points to your VPS IP and port 8000.
