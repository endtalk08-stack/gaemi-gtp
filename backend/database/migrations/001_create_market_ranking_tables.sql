-- Phase 1: Kiwoom market-ranking source data.
-- One snapshot represents one ranking list collected at a particular time.

CREATE TABLE market_instruments (
    market TEXT NOT NULL CHECK (market IN ('KR', 'US')),
    symbol TEXT NOT NULL,
    display_name TEXT NOT NULL,
    exchange TEXT,
    sector TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (market, symbol)
);

CREATE TABLE market_rank_snapshots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'kiwoom',
    market TEXT NOT NULL CHECK (market IN ('KR', 'US')),
    rank_type TEXT NOT NULL CHECK (
        rank_type IN ('popularity', 'trading_value', 'gainers', 'losers')
    ),
    captured_at TIMESTAMPTZ NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_payload JSONB,
    UNIQUE (source, market, rank_type, captured_at)
);

CREATE TABLE market_rank_entries (
    snapshot_id BIGINT NOT NULL REFERENCES market_rank_snapshots(id) ON DELETE CASCADE,
    rank SMALLINT NOT NULL CHECK (rank BETWEEN 1 AND 20),
    market TEXT NOT NULL CHECK (market IN ('KR', 'US')),
    symbol TEXT NOT NULL,
    display_name TEXT NOT NULL,
    price NUMERIC(20, 6),
    change_rate NUMERIC(12, 6),
    trading_value NUMERIC(24, 2),
    volume BIGINT,
    rank_change SMALLINT,
    entry_payload JSONB,
    PRIMARY KEY (snapshot_id, rank),
    FOREIGN KEY (market, symbol)
        REFERENCES market_instruments(market, symbol)
);

CREATE INDEX market_rank_snapshots_lookup_idx
    ON market_rank_snapshots (market, rank_type, captured_at DESC);

CREATE INDEX market_rank_entries_symbol_idx
    ON market_rank_entries (market, symbol);
