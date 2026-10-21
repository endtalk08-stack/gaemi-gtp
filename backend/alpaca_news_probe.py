"""TEMPORARY read-only NVDA news headline export; not part of the news worker."""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

START = "2026-10-20T01:05:24Z"
END = "2026-10-21T01:05:24Z"
DEST = "/tmp/gaemi_alpaca_nvda_20261020_21_review.json"

def main():
    key = (os.environ.get("APCA_API_KEY_ID") or "").strip()
    secret = (os.environ.get("APCA_API_SECRET_KEY") or "").strip()
    if not key or not secret:
        print("NVDA_TEMP_ERROR=missing_api_credentials", flush=True)
        return 2
    articles = []
    token = ""
    seen = set()
    for page_num in range(1, 6):
        params = {"symbols":"NVDA","start":START,"end":END,"sort":"desc","limit":50,"include_content":"true"}
        if token:
            params["page_token"] = token
        address = "https://data.alpaca.markets/v1beta1/news?" + urllib.parse.urlencode(params)
        req=urllib.request.Request(address, headers={
            "APCA-API-KEY-ID":key, "APCA-API-SECRET-KEY":secret,
            "Accept":"application/json", "User-Agent":"gaemigtp-nvda-temporary-review/1.0",
        },method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload=json.loads(resp.read(6000000))
        except urllib.error.HTTPError as exc:
            print("NVDA_TEMP_ERROR=http_"+str(exc.code),flush=True)
            return 3
        except (urllib.error.URLError,TimeoutError,ValueError,OSError):
            print("NVDA_TEMP_ERROR=request_or_json",flush=True)
            return 4
        items=payload.get("news")
        if not isinstance(items,list):
            print("NVDA_TEMP_ERROR=unexpected_news_schema",flush=True)
            return 5
        for item in items:
            if not isinstance(item,dict):
                continue
            ident=str(item.get("id") or item.get("url") or "")
            if ident in seen: continue
            seen.add(ident)
            articles.append(item)
        token=str(payload.get("next_page_token") or "")
        if not token: break
    # This is an isolated 0600 temporary file; no Neon/Render writes and no worker changes.
    path=pathlib.Path(DEST)
    fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as fh:
        json.dump({"symbol":"NVDA","start_utc":START,"end_utc":END,
                   "articles":articles,"next_page_token_remaining":bool(token)},fh,ensure_ascii=False)
    print("NVDA_TEMP_SAVED="+str(path),flush=True)
    print("NVDA_TEMP_COUNT="+str(len(articles)),flush=True)
    for idx,item in enumerate(articles,1):
        content=str(item.get("content") or "")
        info={
           "n":idx,"headline":str(item.get("headline") or "")[:350],
           "source":str(item.get("source") or "")[:100],
           "created_at":str(item.get("created_at") or "")[:40],
           "url":str(item.get("url") or "")[:900],
           "content_chars":len(content),
           "symbols":(item.get("symbols") or [])[:12],
        }
        print("NVDA_TEMP_ARTICLE="+json.dumps(info,ensure_ascii=False),flush=True)
    print("NVDA_TEMP_DONE",flush=True)
    return 0

if __name__=="__main__":
    sys.exit(main())
