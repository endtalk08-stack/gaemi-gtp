-- Additive diagnostic fields. Never store raw AI responses, prompts, URLs or secrets.
-- Existing historical failures remain NULL (reason was not recorded).
ALTER TABLE news_ai_call_ledger
  ADD COLUMN IF NOT EXISTS failure_category TEXT;
ALTER TABLE news_ai_call_ledger
  ADD COLUMN IF NOT EXISTS failure_reason TEXT;
