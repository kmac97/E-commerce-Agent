# 🗺️ E-commerce AI Agent — Roadmap

---

## ✅ Phase 1 — Foundation (Now)
**Goal:** Everything connected, agents running, Telegram working, dashboard live.

- [x] Project structure
- [x] README and docs
- [ ] Supabase tables created
- [ ] FastAPI backend running on Hostinger VPS
- [ ] OpenRouter + Hermes 3 connected
- [ ] First agent working (Researcher)
- [ ] Telegram bot running (basic commands)
- [ ] Web dashboard deployed to Vercel
- [ ] `.env` configured with all keys

**You get:** A live system you can talk to from Telegram and see in your browser.

---

## 🔜 Phase 2 — Research Intelligence
**Goal:** The agent can research products and niches autonomously, score them, and save results.

- [ ] Product research agent (full)
- [ ] Niche finder with scoring (1–10)
- [ ] Competitor snapshot (brand name or URL input)
- [ ] Trending product detection (Serper + TikTok search)
- [ ] Results saved to Supabase
- [ ] Dashboard shows research history
- [ ] Telegram: `/research posture correctors` → full report sent to phone

**You get:** A real research tool. Ask it to research any product, it goes and does it.

---

## 🔜 Phase 3 — Shopify Integration
**Goal:** The agent can manage your Shopify store directly.

- [ ] Shopify API connected
- [ ] Create and edit product listings
- [ ] Optimise product titles and descriptions
- [ ] Monitor orders and inventory
- [ ] Automated low-stock alerts via Telegram
- [ ] Price monitoring and adjustment suggestions
- [ ] Telegram: `/orders` → today's orders summary

**You get:** The agent manages your store. You approve big decisions, it handles the rest.

---

## 🔜 Phase 4 — Marketing Automation
**Goal:** The agent creates and manages your ad campaigns.

- [ ] Meta Ads API connected
- [ ] TikTok Ads API connected
- [ ] Ad copy generator (headlines, body, CTA)
- [ ] UGC script writer
- [ ] Hook generator (10 variations per product)
- [ ] Campaign performance reports
- [ ] Underperforming ad alerts
- [ ] Telegram: `/ad-report` → today's Meta spend and ROAS

**You get:** The agent writes your ads and tells you what's working.

---

## 🔜 Phase 5 — Customer Operations
**Goal:** The agent handles customer communication autonomously.

- [ ] Gmail API connected
- [ ] Auto-read and categorise incoming emails
- [ ] Draft replies for approval or auto-send
- [ ] Refund and return response templates
- [ ] Shipping delay notifications
- [ ] Review monitoring (Shopify + Judge.me)
- [ ] Auto-respond to positive reviews
- [ ] Flag negative reviews for your attention
- [ ] Telegram: `/reviews` → today's reviews summary

**You get:** Customer support runs itself. You only handle escalations.

---

## 🔜 Phase 6 — Full Autonomy & Intelligence
**Goal:** The system runs the business day-to-day with minimal input from you.

- [ ] Scheduled daily briefing via Telegram (revenue, orders, ad spend, issues)
- [ ] Weekly performance report to email
- [ ] P&L tracking and margin alerts
- [ ] Agent memory using pgvector (Supabase) — remembers every decision
- [ ] Multi-store support
- [ ] Supplier research and outreach drafts
- [ ] Business health score (daily)
- [ ] Anomaly detection (sudden traffic drop, spike in refunds, etc.)

**You get:** A business that largely runs itself. You make the big calls, the agent does the work.

---

## Timeline

| Phase | Effort | Dependency |
|-------|--------|-----------|
| Phase 1 | 1–2 sessions | OpenRouter key, Telegram bot, Supabase |
| Phase 2 | 2–3 sessions | Serper API key |
| Phase 3 | 2–3 sessions | Shopify store live |
| Phase 4 | 3–4 sessions | Meta/TikTok developer access |
| Phase 5 | 2–3 sessions | Gmail API credentials |
| Phase 6 | 2–3 sessions | All above complete |
