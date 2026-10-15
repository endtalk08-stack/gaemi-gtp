-- Derived result cache. Does not alter existing article, AI, or news tables.
CREATE TABLE IF NOT EXISTS public.news_processed_snapshots (
    market TEXT NOT NULL CHECK (market IN ('국내', '미국')),
    stock_name TEXT NOT NULL,
    result_limit INTEGER NOT NULL CHECK (result_limit > 0 AND result_limit <= 100),
    storyboard_limit INTEGER NOT NULL CHECK (storyboard_limit > 0 AND storyboard_limit <= 20),
    display_timezone TEXT NOT NULL,
    source_fingerprint CHAR(64) NOT NULL,
    result_payload JSONB NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '24 hours'),
    PRIMARY KEY (market,stock_name,result_limit,storyboard_limit,display_timezone)
);
CREATE INDEX IF NOT EXISTS news_processed_snapshots_expires_idx
    ON public.news_processed_snapshots (expires_at);
