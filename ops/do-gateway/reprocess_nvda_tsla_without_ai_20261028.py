"""Re-run only NVIDIA and Tesla with deployed selection rules; save their two Neon snapshots.
No AI calls, no Render changes, no data deletion, no worker schedule changes.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
os.environ["GAEMIGTP_NEWS_WORKER"] = "1"
os.environ["GAEMIGTP_NEWS_AI_PAUSED"] = "1"
os.environ["NEWS_TRANSLATION_ENABLED"] = "0"
sys.path.insert(0, "/opt/gaemigtp-news/app")

ROOT = Path("/opt/gaemigtp-news/app")
source = (ROOT / "backend/services/news_signal_enrichment.py").read_bytes()
blob = hashlib.sha1(b"blob " + str(len(source)).encode() + bytes([0]) + source).hexdigest()
expected = "15d4e850dc2cd3b9691af5ae909c183f991093c8"
if blob != expected:
    raise SystemExit("STOP_SELECTOR_VERSION_MISMATCH expected=" + expected + " actual=" + blob)
text = source.decode("utf-8")
if any(x in text for x in ("for old in previous or []:", "if issue_id in selected:")):
    raise SystemExit("STOP_REMOVED_BEHAVIOR_STILL_PRESENT")
if "selected.append(entry)" not in text:
    raise SystemExit("STOP_SELECTOR_STRUCTURE_CHANGED")

from backend.services import news_feed
from backend.services import news_processed_store as store
from backend.services.news_result import build_stock_news_result

if not store.database_url():
    raise SystemExit("STOP_DATABASE_URL_UNAVAILABLE")
params = dict(market="미국", limit=50, storyboard_limit=3,
              display_timezone="Asia/Seoul")
prepared = []
for stock in ("엔비디아", "테슬라"):
    raw = news_feed.fetch_stock_news(stock, market="미국", limit=50, raise_on_error=True)
    if not raw or len(raw) > 50:
        raise SystemExit("STOP_NEWS_COUNT_INVALID stock=" + stock)
    result = build_stock_news_result(stock, raw_news_list=raw, **params)
    if result.get("_news_status") != "ok" or result.get("_issue_selection_revision") != 2:
        raise SystemExit("STOP_ANALYSIS_STATUS_INVALID stock=" + stock)
    briefs = result.get("issue_briefs") or []
    if not briefs or len(briefs) > len(raw):
        raise SystemExit("STOP_ISSUE_COUNT_INVALID stock=" + stock)
    if not all(isinstance(item, dict) and item.get("issue_id")
               and item.get("selected_events") and item.get("source_articles") for item in briefs):
        raise SystemExit("STOP_ISSUE_EVIDENCE_INVALID stock=" + stock)
    fingerprint = store.source_fingerprint(raw)
    prior = store.read_snapshot(stock, **params) or {}
    print("REPROCESS_PREPARED " + json.dumps({
        "stock": stock, "fetched": len(raw), "new_selected": len(briefs),
        "previous_db_selected": len(prior.get("_code_issue_briefs") or []),
        "rejected": len(result.get("_issue_selection_rejections") or []),
        "paid_ai_calls": 0}, ensure_ascii=False), flush=True)
    prepared.append((stock, fingerprint, result, len(briefs)))

for stock, fingerprint, result, expected_count in prepared:
    store.save_snapshot(stock, fingerprint=fingerprint, result=result, **params)
    saved = store.read_snapshot(stock, **params)
    if not isinstance(saved, dict):
        raise SystemExit("STOP_POST_SAVE_READ_FAILED stock=" + stock)
    actual = len(saved.get("_code_issue_briefs") or [])
    print("REPROCESS_SAVED " + json.dumps({
        "stock": stock, "db_selected": actual,
        "expected": expected_count,
        "database_write": "own_snapshot_only",
        "paid_ai_calls": 0}, ensure_ascii=False), flush=True)
    if actual != expected_count:
        raise SystemExit("STOP_POST_SAVE_COUNT_MISMATCH stock=" + stock)
print("NVDA_TSLA_REPROCESS_COMPLETE", flush=True)
