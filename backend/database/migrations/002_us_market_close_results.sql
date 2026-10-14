-- One ready-to-display US close result per NY trading date.
-- Kept independent of existing ranking tables and article metadata caches.
-- Apply through Neon's reviewed migration flow before enabling scheduled reads.

CREATE TABLE IF NOT EXISTS us_market_close_results (
    session_date DATE PRIMARY KEY,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source TEXT NOT NULL DEFAULT 'yahoo_daily+naver',
    index_count SMALLINT NOT NULL CHECK (index_count >= 3),
    article_count SMALLINT NOT NULL CHECK (article_count >= 1),
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object')
);
