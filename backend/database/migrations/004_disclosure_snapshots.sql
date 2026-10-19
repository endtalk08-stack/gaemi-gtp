-- Temporary disclosure snapshot only (24h TTL; refreshed rolling 30-day filings).\n-- The reader ignores records after 24h and the DigitalOcean collector prunes\n-- expired snapshots after each successful collection. No long-term history table.\n-- No changes to news tables.
CREATE TABLE IF NOT EXISTS public.disclosure_snapshots (
    market text NOT NULL CHECK (market IN ('KR', 'US')),
    symbol text NOT NULL,
    filings jsonb NOT NULL CHECK (jsonb_typeof(filings) = 'array'),
    fetched_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol)
);
CREATE INDEX IF NOT EXISTS disclosure_snapshots_fetched_idx
    ON public.disclosure_snapshots(fetched_at DESC);
