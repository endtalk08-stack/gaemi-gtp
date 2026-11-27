# US daily chart data flow

## Data path

1. `backend.kiwoom_us_daily_collector` collects the verified US trading-value TOP 20 daily candles from Kiwoom.
2. It validates OHLCV rows and writes them to the existing Neon table `public.us_daily_candles`.
3. After the database write, it reads the latest 120 daily candles per selected symbol and POSTs a snapshot to the existing Pages project.
4. `functions/internal/us-daily-chart-snapshot.js` authenticates the server request and writes `charts/us/{SYMBOL}/daily.json` to the existing `DATA_R2` bucket.
5. `functions/market/us-daily-chart.js` remains read-only and serves the R2 snapshot to the chart widget.

Neon is the collection/validation record. R2 is the website chart read source. The website does not query Neon.

## Required secret configuration (not committed)

Set the same randomly generated token (at least 32 characters) in both environments:

- Cloudflare Pages production secret: `CHART_SYNC_TOKEN`
- DigitalOcean `/etc/gaemigtp/news-worker.env`:
  - `GAEMIGTP_CHART_SYNC_URL=https://gaemigtp-main.pages.dev/internal/us-daily-chart-snapshot`
  - `GAEMIGTP_CHART_SYNC_TOKEN=<same secret value>`

Do not put the token in GitHub, source files, request JSON, logs, or chat.

## Dedicated schedule

The isolated systemd units are:

- `gaemigtp-us-daily-chart.service`
- `gaemigtp-us-daily-chart.timer`

The timer runs weekdays at 16:25 America/New_York, after the collector's 16:15 refresh-window guard. It does not restart or modify `gaemigtp-news.service`.

These unit files are source artifacts only. They are **not installed on the DigitalOcean server by this PR**. Server installation, secret configuration, timer activation, and the first real collection are separate operations requiring explicit approval through the existing DigitalOcean gateway.

## Verification

- Pages Function tests validate authentication, snapshot shape, OHLCV consistency, and R2 writes using a test binding.
- The existing chart GET API remains the read-only contract: `symbol`, `interval=daily`, and up to 120 valid OHLCV rows.
- After approved server setup, verify the timer state and its first execution logs, then call `/market/us-daily-chart?symbol=NVDA` and confirm the returned latest date matches the collected Neon row.
