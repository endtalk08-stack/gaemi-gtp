PostgreSQL schema and migration files live here.

## Phase 1 — Kiwoom ranking source data

`migrations/001_create_market_ranking_tables.sql` creates the first minimum
schema for Korea and US Top 20 lists:

- `market_instruments`: the stock identity and its display metadata.
- `market_rank_snapshots`: one captured ranking list, such as Korean popular
  stocks or US trading-value leaders.
- `market_rank_entries`: the up-to-20 stocks in that list at that moment.

The collector will upsert an instrument first, then save its snapshot and
entries. `source_payload` and `entry_payload` preserve the source response for
future fields without inventing data.

No application database dependency or connection string is committed to the
repository. Neon migrations are applied through its reviewed migration flow.
