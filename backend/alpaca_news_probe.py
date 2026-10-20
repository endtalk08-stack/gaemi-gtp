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
        "end": "2026-10-20T09:00:00Z",
        "sort": "asc", "limit": 50,
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
    key,secret=os.getenv("APCA_API_KEY_ID","").strip(),os.getenv("APCA_API_SECRET_KEY","").strip()
    if not key or not secret:
        print("US_CLOSE_NEWS_ERROR=missing_credentials", flush=True)
        return 2
    print("US_CLOSE_NEWS_SCOPE=Oct_19_post_close_to_Oct_20_0900UTC_two_readonly_gets",flush=True)
    count=0
    match=re.compile(r"\b(?:Wall Street|U\.S\.\s+stocks|US stocks|U\.S\.\s+equities|S&P\s*500|Nasdaq|Dow Jones|Dow\s+futures|Stock market|market close|closing bell|stocks closed|stocks finish|stocks end|stocks fall|stocks rise|equities close|stocks rally|stocks slide|market selloff|market rebound|market recap)\b",re.I)
    seen=set()
    for label,symbols in [("etf_symbols","SPY,QQQ,DIA"),("general_news","")]:
        items=search(key,secret,symbols,label)
        if items is None: continue
        local=0
        for article in items:
            if not isinstance(article,dict):continue
            title=clean(article.get("headline"))
            body=clean(article.get("content"))
            if not title or not match.search(title) or len(body)<500:continue
            u=str(article.get("url") or "").strip()
            if u in seen:continue
            seen.add(u)
            local+=1
            if local>7:continue
            print("US_CLOSE_NEWS_CANDIDATE="+json.dumps({
                "group":label,"published_utc":str(article.get("created_at") or "")[:32],
                "source":str(article.get("source") or "")[:35],
                "headline":title[:200],
                "symbols":(article.get("symbols") or [])[:12],
                "body_chars":len(body),"body_words":len(body.split()),
                "preview":body[:165],"url":u[:350],
            },ensure_ascii=False),flush=True)
        print("US_CLOSE_NEWS_RELEVANT="+label+":"+str(local),flush=True)
        count+=local
    print("US_CLOSE_NEWS_TOTAL_RELEVANT="+str(count),flush=True)
    print("US_CLOSE_NEWS_AUDIT_COMPLETE",flush=True)
    return 0 if count else 5

if __name__ == "__main__":
    sys.exit(main())
