"""No-network, no-AI verification of live US news identity expansion."""
import sys
from unittest.mock import patch
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.services.news_identity_registry import resolve_us_news_identity
from backend.services.news_feed import fetch_stock_news

cases = [
    ("TSMC ADR", "TSMC", "TSM", {"TSMC ADR", "TSMC", "TSM", "taiwan semiconductor"}),
    ("아마존닷컴", "아마존", "AMZN", {"아마존닷컴", "아마존", "AMZN", "amazon"}),
    ("팔란티어 테크놀로지스", "팔란티어", "PLTR", {"팔란티어 테크놀로지스", "팔란티어", "PLTR", "palantir"}),
    ("알파벳 Class A", "알파벳", "GOOGL", {"알파벳 Class A", "알파벳", "GOOGL", "GOOG", "google"}),
    ("ASML 홀딩 ADR", "ASML", "ASML", {"ASML 홀딩 ADR", "ASML"}),
]
for display, canonical, ticker, expected in cases:
    item = resolve_us_news_identity(display)
    assert item["news_name"] == canonical, (display, item)
    assert item["ticker"] == ticker, (display, item)
    assert {x.casefold() for x in expected} <= {x.casefold() for x in item["search_terms"]}, (display, item)
    with patch("backend.services.news_feed._fetch_queries", return_value=[]) as nav, \
         patch("backend.services.news_feed.official_company_news.fetch_company_news", return_value=[]) as official, \
         patch("backend.services.news_feed.sec_filings.fetch_recent_filings", return_value=[]) as sec:
        assert fetch_stock_news(display, limit=50, market="미국") == []
        assert nav.call_args.args[0] == item["search_terms"]
        assert official.call_args.args[0] == canonical
        assert sec.call_args.args[0:2] == (canonical, ticker)
    print("IDENTITY_PASS=%s ticker=%s query_count=%d status=%s" % (
        display, ticker, len(item["search_terms"]), item["status"]), flush=True)
unknown = resolve_us_news_identity("임시 검증용 미등록 종목")
assert unknown["snapshot_names"] == ["임시 검증용 미등록 종목"]
print("UNVERIFIED_NEVER_CROSS_JOINS=True", flush=True)
print("NO_EXTERNAL_REQUESTS_NO_AI=True", flush=True)
