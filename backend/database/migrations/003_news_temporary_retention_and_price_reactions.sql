-- News storage policy v2: raw source metadata is a temporary staging area.
-- Derived issues remain in news_events/news_ai_issues; price reactions stay separate.
-- Explicit processing proof is mandatory before any source row becomes purgeable.
ALTER TABLE news_articles
  ADD COLUMN IF NOT EXISTS retention_expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '7 days');
ALTER TABLE news_articles
  ADD COLUMN IF NOT EXISTS processing_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE news_articles
  ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ;
ALTER TABLE news_articles
  ADD CONSTRAINT news_articles_processing_status_check
  CHECK (processing_status IN ('pending','processed'));
CREATE INDEX IF NOT EXISTS news_articles_safe_retention_idx
  ON news_articles (retention_expires_at, id)
  WHERE processing_status = 'processed' AND processed_at IS NOT NULL;
-- Future derived performance records, no automatic collection until policy is approved.
CREATE TABLE IF NOT EXISTS news_price_reactions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_id BIGINT NOT NULL REFERENCES news_events(id),
  market TEXT NOT NULL CHECK (market IN ('KR','US')),
  symbol TEXT NOT NULL,
  metric_window TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (event_id, market, symbol, metric_window, observed_at)
);
CREATE INDEX IF NOT EXISTS news_price_reactions_lookup_idx
 ON news_price_reactions (market, symbol, observed_at DESC);
