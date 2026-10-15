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

## News staging and eventual derived results

- Migration 002 creates separate source metadata, categories, events, AI issues, and daily AI-call ledger.
- Migration 003 adds a **temporary staging expiration** (7 days from ingestion) and an empty, inactive price-reaction table.
- Migration 004 stores durable source URL evidence in `news_issue_evidence`, independent of temporary source rows.
- Only metadata (headline, short description, URL, publication time, source, market/symbol) is archived. No scraped third-party article body is stored.
- `NEWS_METADATA_STORAGE_ENABLED=1`: opt-in async metadata ingestion via `NEWS_DATABASE_URL`.
- `NEWS_RAW_CLEANUP_ENABLED=1`: run a guarded cleanup after a successful news ingestion, at most once per running server-day.
- A source can be deleted **only when** `retention_expires_at <= now()`, `processing_status='processed'`, and `processed_at IS NOT NULL`. The AI transaction marks processing only after the derived issue and independent URL evidence are saved successfully.
- **Pending/unprocessed sources are never auto-deleted**, even after 7 days. During the trial before permanent analysis fields are finalized, these may accumulate and need explicit policy review.
- Price reaction fields and observation schedules remain unconfigured; no automatic price data is collected or written.
- Redis may be used later for short-lived UI/query caches; it is not the long-term storage for source metadata.
- No cron scheduler is installed: deletion runs when a successful news ingestion triggers the cleanup worker, not at an exact daily clock time.
