-- Adds integrity constraints to the Phase 1 approval-gate tables that were
-- missing them: a unique action_id on approvals (one decision per action --
-- record_approval() in database/client.py now also enforces this at the
-- application layer with a conditional UPDATE, but the DB should guarantee
-- it too), foreign keys so approvals/audit_log can't reference a
-- nonexistent action, and CHECK constraints on the enumerated status/
-- decision/risk_level columns. Run this in Supabase → SQL Editor.
-- Additive only -- does not touch existing rows or other tables.
--
-- If this fails with a uniqueness or foreign-key violation, it means
-- existing data already violates one of these constraints (e.g. a
-- duplicate approval row for the same action) -- inspect and clean that up
-- before re-running, rather than skipping the constraint.

ALTER TABLE approvals
  ADD CONSTRAINT approvals_action_id_unique UNIQUE (action_id),
  ADD CONSTRAINT approvals_action_id_fkey FOREIGN KEY (action_id)
    REFERENCES actions (id) ON DELETE CASCADE,
  ADD CONSTRAINT approvals_decision_check CHECK (decision IN ('approved', 'rejected'));

ALTER TABLE audit_log
  ADD CONSTRAINT audit_log_action_id_fkey FOREIGN KEY (action_id)
    REFERENCES actions (id) ON DELETE CASCADE;

ALTER TABLE actions
  ADD CONSTRAINT actions_status_check
    CHECK (status IN ('proposed', 'approved', 'rejected', 'executed', 'failed')),
  ADD CONSTRAINT actions_risk_level_check
    CHECK (risk_level IN ('low', 'medium', 'high'));
