# US Market Close (staged, not deployed)

- **Source**: Existing NAVER provider query "뉴욕증시 마감".
- **Selection**: Search up to 20 metadata rows, pick up to 8 recent closing articles
  from distinct, explicitly supported publishers, read up to 3 genuine article bodies.
- **AI**: Groq configured in the DO environment, at most **one request per NY session**.
  If fewer than 2 full bodies are accessible, skip generation rather than guessing.
- **Storage**: Neon, migration \`003_us_market_close_editorial.sql\`, one row per US
  market session with 24-hour expiry. Source article **metadata only** is retained
  for internal verification, never full article bodies.
- **Display**: Render \`GET /api/market/us-close\` performs a read-only DB lookup.
  Both the existing central \`#미국장\` button and explicitly asked US market-close
  questions display the saved text without a new AI call.
- **Schedule**: Dedicated systemd service/timer on existing DO server, 07:00 KST.
  Does **not** modify or restart existing \`gaemigtp-news.service\`.
- **Failure**: No fallback AI call, no retries after a claimed session, no
  fabricated current report. Closed/holiday sessions with no matching article
  simply skip. If database or permission unavailable, report unavailable.
- **Permissions**: At initial inspection, the current deployment SSH user
  \`gaemi-news-check\` was allowed to install only the existing news_detail.py.
  It cannot install this independent service or timer. **Do not** bypass
  sudoers or install by modifying the existing news_detail.py. Requires
  separately authorized deployment credentials or a one-time change by the
  server administrator.
- **Privacy/cost**: No new server, no Render AI calls, no additional market-data
  service. AI calls not performed by tests.
