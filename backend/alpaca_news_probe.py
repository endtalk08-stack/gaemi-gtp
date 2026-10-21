"""Read-only one-shot audit of Alpaca US market-close articles (19 Oct 2026).
Two bounded GETs total, output only title, body length, limited excerpt. No DB/UI.
"""
import html
from html.parser import HTMLParser
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

class Strip(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"): self.skip += 1
        elif tag in ("p", "div", "li", "br"): self.parts.append(" ")
    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip: self.skip -= 1
        elif tag in ("p", "div", "li"): self.parts.append(" ")
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)

def clean(value):
    p = Strip()
    p.feed(str(value or "")[:95000])
    return re.sub(r"\s+", " ", html.unescape("".join(p.parts))).strip()

def search(key, secret, symbols, label):
    params = {
        "start": "2026-10-19T20:00:00Z",
        "end": "2026-10-19T23:00:00Z",
        "sort": "desc", "limit": 50,
        "include_content": "true",
        "exclude_contentless": "true",
    }
    if symbols:
        params["symbols"] = symbols
    url = "https://data.alpaca.markets/v1beta1/news?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET", headers={
        "APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
        "Accept": "application/json",
        "User-Agent": "gaemi-us-close-isolated-news-audit/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read(900000))
    except urllib.error.HTTPError as exc:
        print("US_CLOSE_NEWS_ERROR=" + label + "_http_" + str(exc.code), flush=True)
        return None
    except (TimeoutError, urllib.error.URLError, OSError, ValueError):
        print("US_CLOSE_NEWS_ERROR=" + label + "_transport", flush=True)
        return None
    if not isinstance(data, dict) or not isinstance(data.get("news"), list):
        print("US_CLOSE_NEWS_ERROR=" + label + "_schema", flush=True)
        return None
    items = data["news"][:50]
    print("US_CLOSE_NEWS_GROUP=" + json.dumps({
        "group": label, "total": len(items),
        "full_body_500plus": sum(len(clean(a.get("content"))) >= 500 for a in items if isinstance(a, dict)),
        "more_pages": bool(data.get("next_page_token")),
    }), flush=True)
    return items

def main():
    import datetime as dt
    start=dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=24)
    end=dt.datetime.now(dt.timezone.utc)
    iso=lambda t:t.isoformat(timespec="seconds").replace("+00:00","Z")
    key=os.getenv("APCA_API_KEY_ID","").strip()
    secret=os.getenv("APCA_API_SECRET_KEY","").strip()
    if not key or not secret:
        print("ALPACA_24H_ERROR=missing_credentials",flush=True)
        return 2
    print("ALPACA_24H_WINDOW="+iso(start)+".."+iso(end),flush=True)
    all_ok=True
    for sym in ("NVDA","SPCX","AAPL"):
        page_token=None
        seen=set()
        pages=0
        issue=None
        for _ in range(40):
            params={"symbols":sym,"start":iso(start),"end":iso(end),
                    "sort":"asc","limit":50}
            if page_token:params["page_token"]=page_token
            request=urllib.request.Request(
                "https://data.alpaca.markets/v1beta1/news?"+urllib.parse.urlencode(params),
                headers={"APCA-API-KEY-ID":key,"APCA-API-SECRET-KEY":secret,
                         "Accept":"application/json"},
                method="GET")
            try:
                with urllib.request.urlopen(request,timeout=15) as response:
                    data=json.load(response)
            except urllib.error.HTTPError as exc:
                issue="http_"+str(exc.code)
                break
            except (TimeoutError,urllib.error.URLError,OSError,ValueError):
                issue="transport_or_json"
                break
            if not isinstance(data,dict) or not isinstance(data.get("news"),list):
                issue="invalid_schema"
                break
            pages+=1
            for item in data["news"]:
                if isinstance(item,dict):
                    identity=str(item.get("id") or item.get("url") or
                                 item.get("headline") or "")
                    if identity:seen.add(identity)
            page_token=data.get("next_page_token")
            if not page_token:break
        if page_token and issue is None:issue="page_limit_reached"
        if issue:all_ok=False
        print("ALPACA_24H_SYMBOL="+json.dumps(
            {"symbol":sym,"count":len(seen),"pages":pages,
             "complete":issue is None,"error":issue},
            ensure_ascii=False,sort_keys=True),flush=True)
    print("ALPACA_24H_AUDIT_DONE",flush=True)
    return 0 if all_ok else 5

if __name__ == "__main__":
    sys.exit(main())
