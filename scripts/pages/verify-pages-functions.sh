#!/usr/bin/env bash
# Checks Pages Functions and the R2 binding on a deployed site.
# Usage: verify-pages-functions.sh <site-url>
# Uses CF_ACCESS_CLIENT_ID / CF_ACCESS_CLIENT_SECRET when the site is behind
# Cloudflare Access; without them a locked site is reported and skipped.
set -euo pipefail
site="${1:?site url}"
auth=()
if [ -n "${CF_ACCESS_CLIENT_ID:-}" ] && [ -n "${CF_ACCESS_CLIENT_SECRET:-}" ]; then
  auth=(-H "CF-Access-Client-Id: $CF_ACCESS_CLIENT_ID" -H "CF-Access-Client-Secret: $CF_ACCESS_CLIENT_SECRET")
fi
probe="$(curl -sSL --max-redirs 5 --max-time 20 "${auth[@]}" -w '\n%{url_effective}' "$site/market/qqq-reason")"
if grep -Eqi 'Cloudflare Access|cloudflareaccess\.com' <<<"$probe"; then
  if [ "${#auth[@]}" -gt 0 ]; then
    echo "::error::Cloudflare Access rejected the service token at $site."
    exit 1
  fi
  echo "::warning::$site is behind Cloudflare Access and no service token is set; Functions check skipped."
  exit 0
fi
get() { curl -fsS --retry 3 --max-time 20 "${auth[@]}" "$site$1"; }
get /market/qqq-reason | jq -e '.ok == true and (.items | type == "array")'
get /stocks/us/instruments.json |
  jq -e '.ok == true and ([.items[] | select((.symbol == "NVDA" or .symbol == "WMT") and (.industry | length > 0))] | length) == 2'
get "/market/us-daily-chart?symbol=NVDA" | jq -e '.ok == true and .symbol == "NVDA" and (.rows | length > 0)'
