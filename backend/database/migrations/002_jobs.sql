-- Phase 1.5 — durable job queue, replacing BackgroundTasks/asyncio.create_task
-- for run_research_task (which silently vanish if the web process restarts
-- mid-task). Run this in Supabase → SQL Editor. Additive only.

CREATE TABLE jobs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  type TEXT NOT NULL,               -- 'research_task'
  payload JSONB NOT NULL,           -- e.g. {"task_id":..., "topic":..., "research_type":...}
  status TEXT DEFAULT 'pending',    -- pending, running, complete, failed
  attempts INTEGER DEFAULT 0,
  locked_at TIMESTAMPTZ,
  error TEXT
);

-- See 001's matching note: no per-user Supabase auth context in this app,
-- so RLS (auto-enabled by Supabase's SQL editor on new tables) just blocks
-- every insert with no policy to grant it. Disabled to match the rest of
-- the schema.
ALTER TABLE jobs DISABLE ROW LEVEL SECURITY;
