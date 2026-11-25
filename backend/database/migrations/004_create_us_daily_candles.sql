-- US daily candles collected from Kiwoom USA06012.
-- Neon is the source of truth; the Pages/API layer reads these rows.
CREATE TABLE public.us_daily_candles (
    market TEXT NOT NULL CHECK (market IN ('KR', 'US')),
    symbol TEXT NOT NULL,
    session_date DATE NOT NULL,
    open NUMERIC(20, 6) NOT NULL CHECK (open > 0),
    high NUMERIC(20, 6) NOT NULL CHECK (high > 0),
    low NUMERIC(20, 6) NOT NULL CHECK (low > 0),
    close NUMERIC(20, 6) NOT NULL CHECK (close > 0),
    volume BIGINT CHECK (volume IS NULL OR volume >= 0),
    source TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (market, symbol, session_date),
    FOREIGN KEY (market, symbol)
        REFERENCES public.market_instruments(market, symbol),
    CHECK (low <= LEAST(open, close) AND GREATEST(open, close) <= high)
);

CREATE INDEX us_daily_candles_symbol_date_idx
    ON public.us_daily_candles (market, symbol, session_date DESC);
CREATE INDEX us_daily_candles_fetched_idx
    ON public.us_daily_candles (fetched_at DESC);
