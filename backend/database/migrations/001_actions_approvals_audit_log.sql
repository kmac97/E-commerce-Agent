-- Phase 1.1 — approval-gate tables.
-- Run this in Supabase → SQL Editor. Additive only: creates three new
-- tables, does not touch research/agent_tasks/products/competitors/
-- decisions/memories.

-- A proposed action awaiting (or already given) a decision.
CREATE TABLE actions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  type TEXT NOT NULL,               -- 'create_shopify_product', 'update_shopify_product'
  proposing_agent TEXT NOT NULL,    -- 'researcher', 'store_monitor'
  risk_level TEXT DEFAULT 'low',    -- low, medium, high
  status TEXT DEFAULT 'proposed',   -- proposed, approved, rejected, executed, failed
  idempotency_key TEXT UNIQUE,      -- prevents duplicate proposals for the same trigger
  payload JSONB NOT NULL,           -- what's being proposed (new title/description/price, etc.)
  before JSONB,                     -- current state at proposal time, for diffs (update actions)
  result JSONB,                     -- populated after execution (e.g. Shopify product id/url)
  error TEXT
);

-- One approval/rejection decision per action.
CREATE TABLE approvals (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  action_id UUID NOT NULL,
  decision TEXT NOT NULL,           -- 'approved', 'rejected'
  reason TEXT,                      -- rejection reason, feeds back into the next agent attempt
  decided_by TEXT                   -- Telegram chat_id of whoever decided
);

-- Append-only lifecycle trail for every action.
CREATE TABLE audit_log (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  action_id UUID NOT NULL,
  event TEXT NOT NULL,              -- 'proposed', 'approved', 'rejected', 'executed', 'failed'
  detail JSONB
);

-- This app has no per-user Supabase auth context -- one FastAPI backend,
-- one shared key, access gated at the API-key/Telegram-owner layer instead.
-- Supabase's SQL editor auto-enables RLS on new tables by default with no
-- policies, which blocks every insert/update. Disable it here to match the
-- rest of the schema (research/agent_tasks/products/etc., created before
-- that default existed).
ALTER TABLE actions DISABLE ROW LEVEL SECURITY;
ALTER TABLE approvals DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log DISABLE ROW LEVEL SECURITY;
