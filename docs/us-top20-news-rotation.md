# US top-20 news worker: five-minute frozen-rank rotation

**Status:** implementation and offline tests on a nonproduction GitHub branch.
**NOT installed on the DigitalOcean worker.** The active server service entrypoint
and scheduling/selection code must be inspected before this helper can be wired in.

## Incident evidence (read only, 2026-10-25 KST)
- Latest Kiwoom `market_rank_snapshots` US `trading_value` snapshot had exactly
  20 distinct tickers, captured 2026-10-24 08:59 KST.
- `news_processed_snapshots.checked_at` advanced about every five minutes for
  separate tickers, **not** as one entire top-20 batch.
- At 09:18 KST, #2 NVDA, #4 TSLA, #6 META, #8 AMD, #10 AMZN had not been checked
  since 2026-10-24 12:32-12:34 KST, although adjacent ranked symbols had been
  checked. No live scheduler logs or entrypoint were accessible; **do not label
  the root cause as confirmed** based on DB timestamps alone.
- A read-only GitHub Actions audit (run 40146628205) failed before diagnostics
  could be retrieved; the proposed code below is a fix for the required rotation
  semantics, not proof that a particular line on the server caused the skips.

## Contract to integrate with the existing worker
1. Read all 20 ranking entries from **one** latest committed `US/trading_value`
   `market_rank_snapshots.id`; ORDER BY `rank`. Reject incomplete, duplicate,
   or malformed rankings. Use the stock **ticker**, not display name, as identity.
2. Start a frozen cycle with 20 tickers and record its state. Perform exactly
   one stock check every **300 seconds** using the existing worker's stock-news
   collection function. Never also enable a competing timer.
3. Once a cycle starts, rank changes do **not** reorder pending stocks. On the
   21st check, fetch the new top-20 ranking and start a fresh cycle. Thus every
   complete cycle is **20 x 5 = 100 minutes** nominally.
4. Call `us_top20_rotation.plan_tick(state, rank_rows)`, atomically persist the
   returned state **before** invoking the existing worker for the chosen ticker,
   and always call `finish_tick(state, symbol, ok=...)` with its outcome after
   the attempt (even if no new material was found). Persist it atomically.
   On a crash, the still-pending ticker is replayed rather than skipped.
5. Serialize all workers with a process/database lock (e.g. `flock`) so two
   ticks can never advance the same rotation cursor simultaneously. Persist the
   state across restarts using a durable file (atomic rename + fsync) or one DB
   transaction with a lock. `us_top20_rotation` intentionally contains no I/O.
6. A provider failure should record its outcome separately from a successful
   check; it must not block the other 19 positions. Failed symbols recur in
   the next complete cycle. Invalid new ranking falls back to the prior frozen
   complete cycle; it never silently skips or invents symbols.
7. Preserve the existing headline/article quality pipeline unchanged. The US
   issue-list presentation no longer imposes a count-of-three cap; the original
   **24-hour article publication-date** eligibility, verification and dedup rules
   still apply. The news candidate reader remains bounded for operational load.

## What must be verified BEFORE deployment
- SSH read-only `systemctl cat gaemigtp-news.service` and its `ExecStart`.
- Read live worker selector (the actual server code is not in `main`).
- Compare its scheduler/timer with the rule above, identify the exact cause of
  the five skipped tickers, and back up original unit/code.
- Run one cycle in **dry-run mode** with the frozen 20 ticker list, including
  rank swaps (2/3), an incoming/outgoing #20, failure, restart, and empty-news
  check. Validate that no other worker also schedules US stock collection.
- Only then install the selector adapter, preserving existing news processing
  and headline generation. Monitor `checked_at` for all 20 tickers over a full
  100-minute cycle. **No automatic deployment** is defined by this branch.

## Tests on GitHub
- `tests/test_us_top20_rotation.py`: 20-per-cycle, rank changes, no duplicates,
  restart recovery, provider failure, incomplete/duplicate rank rejection.
- `tests/test_us_news_freshness.py`: show all 6 fresh code briefs (and 5 fresh
  AI-channel briefs if requested), filter strictly by original 24-hour timestamps.
- `tests/test_news_central_selection.py`: 4 separately verified US event issues
  survive the historical `storyboard_limit=3` input, while domestic tests
  preserve previous behavior.
- CI run 40146955946: 19 rotation/freshness + 29 selection tests passed.
