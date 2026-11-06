"""Deterministic 4-feed contract tests: fake opener; never connects to TradingView."""
import json
import os
import sys
import tempfile
import time
import urllib.error
from pathlib import Path

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers import tradingview_news_bundle as bundle
from backend.providers.tradingview_news_detail import _extract_detail, enrich_articles
from backend.services.tradingview_news_page import normalize_article, build_snapshot

class FakeReply:
    def __init__(self, data):
        self.content = json.dumps({"success": True, "data": data}).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, _): return self.content

now = time.time()
seen = []
def opener(req, timeout):
    path = req.full_url.split("?")[0]
    seen.append(path)
    assert path.startswith("https://api.tradingviewapi.com/api/news")
    kind = path.rsplit("/", 1)[-1]
    title = {"news": "Markets decline", "stock": "Company earnings rise",
             "economic": "US CPI inflation", "index": "NASDAQ index climbs"}[kind]
    return FakeReply({"items": [
        {"id":kind, "title":title, "published":now, "shortDescription":"DO NOT KEEP",
         "provider":{"name":"Wire"}, "relatedSymbols":[{"symbol":"NASDAQ:AAPL"}] if kind=="stock" else []},
        {"id":"shared", "title":"CPI jobs", "published":now}
    ]})

for category in bundle.CATEGORIES:
    rows = bundle._request_news("fake-key", opener, category)
    assert len(rows)==2 and rows[0]["news_categories"]==[category]
    assert "shortDescription" not in rows[0]
assert seen==[bundle.BASE_URL,bundle.BASE_URL+"/stock",bundle.BASE_URL+"/economic",bundle.BASE_URL+"/index"]

existing=[{"id":"shared","title":"CPI jobs","published":now,"news_categories":["overall"],
           "detail_summary":"API summary", "detail_description":"DO NOT KEEP"}]
fresh=[{"id":"shared","title":"CPI jobs","published":now,"news_categories":["stock"]}]
merged=bundle._merge(fresh, existing, now)
assert len(merged)==1
assert set(merged[0]["news_categories"])=={"overall","stock"}
assert merged[0]["detail_summary"]=="API summary"
assert "detail_description" not in merged[0]
assert normalize_article({"id":"s","title":"Stocks market Company report","news_categories":["stock"]})["news_section"]=="stock"
assert normalize_article({"id":"e","title":"Market CPI inflation","news_categories":["economic"]})["event_category"]["label"]=="경제지표"
assert normalize_article({"id":"i","title":"NASDAQ index rises","news_categories":["index"]})["news_section"]=="market"

article=normalize_article({"id":"a","title":"Company earnings","news_categories":["stock"],
     "detail_summary":"Verified API summary","detail_body":"Complete content","permission":"headline"})
assert article["summary"]=="Verified API summary"
assert article["body"]=="" and "description" not in article
article=normalize_article({"id":"b","title":"Company earnings","news_categories":["stock"],
     "detail_body":"Full permitted content","detail_publication_allowed":True,"permission":"provider"})
assert article["body"]=="Full permitted content"
snapshot=build_snapshot([{"id":"a","title":"Markets CPI","news_categories":["economic"],
                          "summary":"API summary","shortDescription":"BAD"}])
assert snapshot["items"][0]["summary"]=="API summary"
assert "description" not in snapshot["items"][0]
assert _extract_detail({"article":{"content":{"text":"Body text"},"summary":"Summary text"}})=={
    "detail_body":"Body text","detail_summary":"Summary text"}
no_api=lambda *args: (_ for _ in ()).throw(AssertionError("real API attempt"))
rows, stats=enrich_articles([{"id":"zero"}],max_requests=0,api_key="fake",opener=no_api)
assert stats["requested"]==0 and len(rows)==1

# Exercise REAL refresh orchestration with temp cache and fake responses ONLY.
# Save and restore the API setting; live network is impossible (fake opener).
with tempfile.TemporaryDirectory() as td:
    cache_path=bundle.CACHE_PATH
    oldkey=os.environ.get("TRADINGVIEW_API_KEY")
    oldfour=os.environ.get(bundle.FOUR_FEEDS_ENV)
    try:
        bundle.CACHE_PATH=Path(td)/"cached.json"
        os.environ["TRADINGVIEW_API_KEY"]="fake"
        os.environ[bundle.FOUR_FEEDS_ENV]="1"
        old={"feed_version":bundle.FEED_VERSION,"items":[
            {"id":"preserve","title":"Existing story","published":now,
             "news_categories":["overall"]}]}
        bundle.CACHE_PATH.write_text(json.dumps(old))
        def failing(req, timeout):
            if req.full_url.startswith(bundle.BASE_URL+"/economic"):
                raise urllib.error.HTTPError(req.full_url,429,"quota",{},None)
            return opener(req,timeout)
        unchanged=bundle.refresh_news_cache(now=now,opener=failing,force=True)
        assert [x["id"] for x in unchanged]==["preserve"],unchanged
        state=json.loads(bundle.CACHE_PATH.read_text())
        assert [x["id"] for x in state["items"]]==["preserve"]
        assert "economic" in state["failed_categories"] and state["requests_last_refresh"]==4

        # Daily guard must block retries even with force=True.
        block=bundle.refresh_news_cache(now=now+1,opener=no_api,force=True)
        assert [x["id"] for x in block]==["preserve"]
        combined=bundle.refresh_news_cache(now=now+86400,opener=opener,force=True)
        ids=[x["id"] for x in combined]
        assert set(ids)=={"news","stock","economic","index","shared","preserve"}, ids
        shared=next(x for x in combined if x["id"]=="shared")
        assert set(shared["news_categories"])==set(bundle.CATEGORIES)
        assert all("shortDescription" not in x for x in combined)
        state=json.loads(bundle.CACHE_PATH.read_text())
        assert not state["failed_categories"] and state["requests_last_refresh"]==4
        assert state["four_feed_month_requests"]==8
        # Monthly fail-closed protection, even with a forced run.
        state["four_feed_month_requests"]=120
        bundle.CACHE_PATH.write_text(json.dumps(state))
        protected=bundle.refresh_news_cache(now=now+2*86400,opener=no_api,force=True)
        assert len(protected)==6
    finally:
        bundle.CACHE_PATH=cache_path
        if oldkey is None: os.environ.pop("TRADINGVIEW_API_KEY",None)
        else: os.environ["TRADINGVIEW_API_KEY"]=oldkey
        if oldfour is None: os.environ.pop(bundle.FOUR_FEEDS_ENV,None)
        else: os.environ[bundle.FOUR_FEEDS_ENV]=oldfour
print("NEWS_OFFLINE_READINESS_PASS=4 endpoints, atomic fallback, duplicates, classification, summary/body, no descriptions, zero real API calls")
