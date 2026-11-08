"""Offline/no-API/no-R2 verification of installed TradingView news code."""
from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers import tradingview_news_bundle as bundle
from backend.services import tradingview_news_page as page
from backend.services import r2_news_uploader as r2

def inactive():
    for unit in ("gaemigtp-news.service", "gaemigtp-tradingview-news.service"):
        p = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True)
        assert p.stdout.strip() == "inactive", (unit, p.stdout.strip())
inactive()
source = Path(bundle.__file__).read_text(encoding="utf-8")
assert 'categories = ("overall",)' in source and "four_enabled = False" in source
assert bundle.FEED_VERSION == "overall-us-ko-v1"
assert r2.OBJECT_KEY == "news/latest.json"
assert "enrich_articles(" not in Path("/opt/gaemigtp-news/app/backend/tradingview_news_worker.py").read_text(encoding="utf-8")

def story(id, title, symbol=None):
    d = {"id":id, "title":title, "published":1762550000,
         "news_categories":["overall"]}
    if symbol:
        d["relatedSymbols"] = [{"symbol":"NASDAQ:"+symbol}]
    return d

items = [
    story("S1", "Nvidia earnings beat while CPI inflation cools", "NVDA"),
    story("S1", "Nvidia earnings beat while CPI inflation cools", "NVDA"),
    story("M1", "Dollar index and currency rise"),
    story("M2", "Powell signals rate cut"),
    story("M3", "Technology sector sees chip rally"),
    story("OTHER", "Local company announces new campus", "AAPL"),
    story("OTHER2", "Separate story on the same event", "AAPL"),
]
snapshot=page.build_snapshot(items, generated_at="test")
rows={x["id"]:x for x in snapshot["items"]}
assert len(rows)==6 and snapshot["count"]==6, snapshot["count"]
assert rows["S1"]["news_sections"] == ["stock","market"], rows["S1"]["news_sections"]
assert "economic" in [x["code"] for x in rows["S1"]["market_event_matches"]]
assert "stock" in rows["S1"]["news_sections"]
assert rows["OTHER"]["news_sections"] == ["market"], rows["OTHER"]
assert rows["OTHER2"]["id"] != rows["OTHER"]["id"]
codes=[x["code"] for x in rows["M1"]["market_event_matches"]]
assert "fx_commodities" in codes and "rates_bonds" not in codes, codes
assert "fed" in [x["code"] for x in rows["M2"]["market_event_matches"]]
assert "sector" in [x["code"] for x in rows["M3"]["market_event_matches"]]
assert all(x.get("body","") == "" for x in rows.values())
inactive()
print("OFFLINE_TEST_PASS=1 COUNT="+str(snapshot["count"]))
print("TESTS=overall_only,unchanged_cache_version,r2_path,service_paused,id_dedup,dual_classification,market_fallback,separate_ids,fx_vs_rates,fed,sector,no_body_leak,no_detail_calls")
