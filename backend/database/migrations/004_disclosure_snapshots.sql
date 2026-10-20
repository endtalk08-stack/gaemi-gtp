-- Temporary disclosure snapshot only: last 24h filings and 24h TTL.
-- DigitalOcean refreshes each stock, and a separate sweep may delete expired rows.
-- Reader always ignores rows older than 24 hours; no long-term disclosure archive.
-- No changes to news tables.
CREATE TABLE IF NOT EXISTS public.disclosure_snapshots (
    market text NOT NULL CHECK (market IN ('KR', 'US')),
    symbol text NOT NULL,
    filings jsonb NOT NULL CHECK (jsonb_typeof(filings) = 'array'),
    fetched_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol)
);
CREATE INDEX IF NOT EXISTS disclosure_snapshots_fetched_idx
    ON public.disclosure_snapshots(fetched_at DESC);
