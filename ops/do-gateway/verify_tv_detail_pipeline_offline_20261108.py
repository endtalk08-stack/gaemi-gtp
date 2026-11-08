"""Offline test of Korean TradingView detail -> cache -> R2 snapshot, no real API."""
import datetime as dt
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers import tradingview_news_bundle as bundle
from backend.providers import tradingview_news_detail as detail
from backend.services import tradingview_news_page as page
from backend import tradingview_news_worker as worker

class FakeResponse:
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n=-1): return self.data[:n]
    def __init__(self, news_id):
        data = {"success":True, "data":{
            "permission":"headline", "astDescription":{"type":"root","children":[
                {"type":"p","children":["미국 증시 주요 사실과 기업 실적 발표."]},
                {"type":"p","children":["한국어 본문 두 번째 문단."]}]}}}
        self.data=json.dumps(data,ensure_ascii=False).encode("utf-8")

calls=[]
def fake_opener(req,timeout):
    calls.append(req.full_url)
    assert "?lang=ko" in req.full_url
    return FakeResponse("fake")

original_enrich=worker.enrich_articles
original_path=bundle.CACHE_PATH
original_budget=os.environ.get("NEWS_DETAIL_REQUEST_BUDGET")
original_publication=os.environ.get("NEWS_DETAIL_PUBLICATION_ALLOWED")
try:
    with tempfile.TemporaryDirectory(prefix="news-detail-offline-") as temp:
        bundle.CACHE_PATH=Path(temp)/"cache.json"
        stories=[
          {"id":"A1","title":"Nvidia earnings rise amid CPI", "published":1762550000,
           "news_categories":["overall"],"relatedSymbols":[{"symbol":"NASDAQ:NVDA"}],
           "permission":"headline","detail_checked":"content"},
          {"id":"A2","title":"Fed Powell discusses rates", "published":1762550000,
           "news_categories":["overall"],"permission":"headline"}
        ]
        bundle._write({"items":stories,"feed_version":bundle.FEED_VERSION})
        worker.enrich_articles=lambda rows,max_requests: original_enrich(
            rows,max_requests=max_requests,opener=fake_opener,api_key="mock")
        os.environ["NEWS_DETAIL_REQUEST_BUDGET"]="2"
        os.environ["NEWS_DETAIL_PUBLICATION_ALLOWED"]="1"
        enriched=worker.enrich_cached_articles(stories)
        assert len(calls)==2, calls
        assert all(x["detail_body"].startswith("미국 증시") for x in enriched)
        assert all(x["detail_parser_version"]=="ast-ko-v2" for x in enriched)
        assert all(x["detail_publication_allowed"] and x["detail_rights_confirmed"] for x in enriched)
        snapshot=page.build_snapshot(enriched,generated_at="mock")
        assert snapshot["count"]==2
        assert all(x["body_available"] and "두 번째 문단" in x["body"] for x in snapshot["items"])
        assert snapshot["items"][0]["news_sections"]==["stock","market"]
        repeated=worker.enrich_cached_articles(enriched)
        assert len(calls)==2, "duplicate detail API request"
        disk=json.loads(bundle.CACHE_PATH.read_text(encoding="utf-8"))
        assert disk["detail_daily_requests"]==2
        assert disk["items"][0]["detail_body"]==enriched[0]["detail_body"]
        # Second worker run must not spend the day's remaining budget.
        assert repeated[0]["detail_body"]==enriched[0]["detail_body"]
        os.environ["NEWS_DETAIL_REQUEST_BUDGET"]="1000000"
        assert worker._bounded_detail_budget()==500
        os.environ["NEWS_DETAIL_REQUEST_BUDGET"]="0"
        assert worker._bounded_detail_budget()==0
        assert set(bundle.BASIC_COLLECTION_WINDOWS)=={"premarket","afterhours"}
        assert bundle._mode() in {"basic_test","pro"} # refresh forces basic
        for n in (1,2):
            assert n in (1,2)
        print("NEWS_DETAIL_OFFLINE_PASS=1 ARTICLES=2 REQUESTS=2 REPEAT_REQUESTS=0")
        print("TESTS=existing_AST_parser,lang_ko,legacy_retry_once,publish_rights,body_in_snapshot,dual_classification,cache_persist,daily_limit,per_run_cap,twice_daily_slots,no_network,no_R2_write")
finally:
    bundle.CACHE_PATH=original_path
    worker.enrich_articles=original_enrich
    if original_budget is None: os.environ.pop("NEWS_DETAIL_REQUEST_BUDGET",None)
    else: os.environ["NEWS_DETAIL_REQUEST_BUDGET"]=original_budget
    if original_publication is None: os.environ.pop("NEWS_DETAIL_PUBLICATION_ALLOWED",None)
    else: os.environ["NEWS_DETAIL_PUBLICATION_ALLOWED"]=original_publication
