-- Separate 30-day disclosure read model; no changes to news tables.
CREATE TABLE IF NOT EXISTS public.disclosure_snapshots (
    market text NOT NULL CHECK (market IN ('KR', 'US')),
    symbol text NOT NULL,
    filings jsonb NOT NULL CHECK (jsonb_typeof(filings) = 'array'),
    fetched_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (market, symbol)
);
CREATE INDEX IF NOT EXISTS disclosure_snapshots_fetched_idx
    ON public.disclosure_snapshots(fetched_at DESC);
