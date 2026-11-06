"""One strictly bounded read-only TradingView Data API detail verification.
Uses existing local bundle. Never prints article text or credentials.
Does not mutate caches, R2, database or service state.
"""
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
import urllib.error

CACHE = Path("/var/lib/gaemigtp-news/tradingview-news-bundle.json")
URL = "https://api.tradingviewapi.com/api/news/"

def main():
    key = os.environ.get("TRADINGVIEW_API_KEY", "").strip()
    if not key:
        print("DETAIL_CHECK=missing_api_key")
        return
    if not CACHE.is_file() or CACHE.is_symlink():
        print("DETAIL_CHECK=missing_cache")
        return
    obj = json.loads(CACHE.read_text(encoding="utf-8"))
    items = obj.get("items") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        print("DETAIL_CHECK=invalid_cache")
        return
    selected = next((x for x in items if isinstance(x,dict)
                     and x.get("id") and x.get("permission") != "headline"), None)
    if not selected:
        print("DETAIL_CHECK=no_eligible_ids")
        return
    news_id = str(selected["id"])
    req = urllib.request.Request(
        URL+urllib.parse.quote(news_id,safe=""),
        headers={"Authorization":"Bearer "+key,"Accept":"application/json","User-Agent":"gaemiGTP-news-worker/1.0"},
    )
    try:
        with urllib.request.urlopen(req,timeout=12) as f:
            reply = json.loads(f.read(250000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print("DETAIL_CHECK=http_error status=%d" % exc.code)
        return
    except (OSError,ValueError,UnicodeError) as exc:
        print("DETAIL_CHECK=error type=%s" % type(exc).__name__)
        return
    data = reply.get("data") if isinstance(reply,dict) else None
    print("DETAIL_CHECK=ok success=%s data_type=%s" % (
        reply.get("success") if isinstance(reply,dict) else None,
        type(data).__name__,
    ))
    if isinstance(data,dict):
        print("DETAIL_KEYS="+",".join(sorted(data.keys())[:40]))
        for field in ("body","articleBody","article_body","bodyText","fullText","full_text","content","text","storyText","description","shortDescription","summary","permission","paywall"):
            value=data.get(field)
            if value is not None:
                print("DETAIL_FIELD name=%s type=%s size=%d" % (
                    field,type(value).__name__,len(str(value)),
                ))
        for name in ("item","story","news","article"):
            obj=data.get(name)
            if isinstance(obj,dict):
                print("DETAIL_NESTED name=%s keys=%s" % (name,",".join(sorted(obj.keys())[:40])))
if __name__=="__main__":
    main()
