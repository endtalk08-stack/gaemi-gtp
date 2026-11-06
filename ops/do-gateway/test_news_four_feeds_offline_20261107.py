"""Offline, fake-opener only checks. ZERO paid API calls and ZERO cache writes."""
import datetime as dt
import json
import os
import sys
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers import tradingview_news_bundle as bundle
from backend.providers.tradingview_news_detail import enrich_articles
from backend.services.tradingview_news_page import normalize_article, build_snapshot

class FakeReply:
    def __init__(self, data): self.content = json.dumps({"success":True,"data":data}).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, _): return self.content

seen=[]
def opener(req, timeout):
    path=req.full_url.split("?")[0]
    seen.append(path)
    assert "api.tradingviewapi.com" in path
    label=path.rsplit("/",1)[-1]
    return FakeReply({"items":[{"id":label, "title":"CPI jobs inflation" if label=="economic" else "Stock shares increased", "published":1794000000,
                         "relatedSymbols":[{"symbol":"NASDAQ:AAPL"}] if label=="stock" else []}]})
for category in bundle.CATEGORIES:
    rows=bundle._request_news("fake-key",opener,category)
    assert len(rows)==1 and rows[0]["news_categories"]==[category]
assert seen==[bundle.BASE_URL,bundle.BASE_URL+"/stock",bundle.BASE_URL+"/economic",bundle.BASE_URL+"/index"],seen
existing=[{"id":"one","title":"Test company earnings","published":1794000000,"news_categories":["stock"],"detail_summary":"Provider original summary","detail_description":"Description"}]
fresh=[{"id":"one","title":"Test company earnings","published":1794000000,"news_categories":["overall"]}]
merged=bundle._merge(fresh,existing,1794000001)
assert len(merged)==1 and set(merged[0]["news_categories"])=={"overall","stock"}
assert merged[0]["detail_summary"]=="Provider original summary"
assert normalize_article({"id":"e","title":"Jobs report","news_categories":["economic"]})["news_section"]=="market"
assert normalize_article({"id":"i","title":"Dow climbs","news_categories":["index"]})["news_section"]=="market"
assert normalize_article({"id":"s","title":"Company earnings","news_categories":["stock"]})["news_section"]=="stock"
item=normalize_article({"id":"x","title":"Test stock earnings","news_categories":["stock"],"detail_summary":"Real summary","detail_description":"Real description","detail_body":"Raw content","permission":"headline"})
assert item["summary"]=="Real summary" and item["description"]=="Real description" and item["body"]==""
rows,stat=enrich_articles([{"id":"no-network"}],max_requests=0,api_key="fake",opener=lambda *args: (_ for _ in ()).throw(AssertionError("API called")))
assert stat["requested"]==0 and len(rows)==1
assert os.getenv(bundle.FOUR_FEEDS_ENV,"").strip()!="1", "Do not run offline test while 4-feed mode enabled"
print("NEWS_FOUR_FEEDS_OFFLINE_PASS=4 endpoints, dedup, categories, field mapping, zero API calls", flush=True)
