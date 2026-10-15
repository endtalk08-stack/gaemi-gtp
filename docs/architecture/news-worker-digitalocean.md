# News worker — safe staged cutover

Flow: DigitalOcean worker -> Neon news_processed_snapshots -> Render reads -> existing UI.

- This branch does NOT deploy to DigitalOcean and does NOT enable the read switch on Render.
- Original Naver News, company filings, and existing scoring/storyboard/issue rules are unchanged.
- A configured list of watched stocks is mandatory (NEWS_WORKER_STOCKS), max 30 until measured.
- Existing NEWS_DATABASE_URL and Naver credentials must be securely configured on the worker. Never commit secrets.
- Worker polls every 5 minutes by default. If the source fingerprint is unchanged, expensive analysis is skipped.
- Only successful, existing stock-news output is stored. Results expire after 24 hours, with an explicit cleanup.
- In the modified shared news reader, NEWS_PROCESSED_READ_MODE=off is the default (unchanged behavior).
- Mode prefer: read a fresh Neon snapshot first, fall back to old Render analysis on cache miss.
- Mode only: read fresh Neon snapshots, otherwise return an empty error result. DO NOT enable until all needed stocks are covered.
- Real cutover requires SQL migration approval, secure worker deployment/credentials, verification of write/read results and a rollback check.
- The existing /analyze endpoint still attaches price reactions on Render; moving that work is NOT completed in this stage.
- Other news endpoints (e.g. the US close brief) are NOT migrated in this stage.
- Do not enable paid DigitalOcean backups, new servers, Redis or other paid services.
