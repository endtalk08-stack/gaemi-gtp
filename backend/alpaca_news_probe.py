"""Read-only probe of the Alpaca (Benzinga) news feed: recent headlines and volume.
GET only, prints headline / source / time / symbols. No storage, no publishing.
Run by the gateway operation alpaca-news-verify with /etc/gaemigtp/alpaca.env.
"""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def fetch(key, secret, start, end, token=None):
    params = {"start": start, "end": end, "sort": "desc", "limit": 50, "include_content": "false"}
    if token:
        params["page_token"] = token
    req = urllib.request.Request("https://data.alpaca.markets/v1beta1/news?" + urllib.parse.urlencode(params),
                                 headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
                                          "Accept": "application/json", "User-Agent": "gaemiGTP-news-probe/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read(2000000))


def main():
    key = os.getenv("APCA_API_KEY_ID", "").strip()
    secret = os.getenv("APCA_API_SECRET_KEY", "").strip()
    if not key or not secret:
        print("ALPACA_NEWS_ERROR=credentials_missing", flush=True)
        return 2
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    start = (now - dt.timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    end = now.isoformat().replace("+00:00", "Z")
    items, token = [], None
    try:
        for _ in range(6):
            data = fetch(key, secret, start, end, token)
            items += data.get("news") or []
            token = data.get("next_page_token")
            if not token:
                break
    except urllib.error.HTTPError as exc:
        print("ALPACA_NEWS_ERROR=http_%d" % exc.code, flush=True)
        return 1
    except Exception as exc:
        print("ALPACA_NEWS_ERROR=" + type(exc).__name__, flush=True)
        return 1
    sources = {}
    for a in items:
        sources[a.get("source") or "?"] = sources.get(a.get("source") or "?", 0) + 1
    print("ALPACA_NEWS_24H count=%d%s sources=%s" % (len(items), "+" if token else "", json.dumps(sources)), flush=True)
    for a in items[:40]:
        print("NEWS %s | %s | %s | %s" % (str(a.get("created_at"))[:16], a.get("author") or a.get("source"),
              ",".join((a.get("symbols") or [])[:4]), str(a.get("headline"))[:160]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
