-- Review-only migration. Apply to Neon before deploying the matching DO writer / Render readers.
-- Historical records are retained for future post-news price-reaction scoring.
-- The 24-hour limit is a DISPLAY filter based on the cited original published_at.
CREATE TABLE IF NOT EXISTS public.news_issue_history (
    id BIGSERIAL PRIMARY KEY,
    market TEXT NOT NULL CHECK (market = 'US'),
    symbol TEXT NOT NULL,
    company_key TEXT NOT NULL,
    source_stock_name TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'code' CHECK (channel = 'code'),
    source_url TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    first_saved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    issue_brief JSONB NOT NULL CHECK (jsonb_typeof(issue_brief) = 'object'),
    CONSTRAINT news_issue_history_same_article_unique UNIQUE (market, symbol, channel, source_url)
);
CREATE INDEX IF NOT EXISTS news_issue_history_active_lookup
    ON public.news_issue_history (market, symbol, published_at DESC);
-- Deliberately NO automatic DELETE / expiry job on this table.
-- news_processed_snapshots retains its existing 24h TTL and remains unchanged.
