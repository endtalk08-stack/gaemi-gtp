-- STAGED ONLY. Review and apply to Neon separately after approval.
-- Preserve the publisher label after raw news_articles retention cleanup.
ALTER TABLE public.news_issue_evidence
    ADD COLUMN IF NOT EXISTS source_publisher text;
