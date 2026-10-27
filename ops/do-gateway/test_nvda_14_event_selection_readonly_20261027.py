"""One-shot, NVIDIA-only, read-only live DigitalOcean 14-family selection test.
Collect at most 50 fresh articles; apply the DEPLOYED existing selector;
report conservative same-event dedup without saving or publishing anything.
"""
import json
import os
import re
import sys
from collections import Counter

sys.dont_write_bytecode = True
os.environ["NEWS_TRANSLATION_ENABLED"] = "0"
os.environ["GAEMIGTP_NEWS_AI_PAUSED"] = "1"
sys.path.insert(0, "/opt/gaemigtp-news/app")

from backend.services import news_feed
from backend.services import news_processed_store as store
from backend.services.news_result import build_stock_news_result
from backend.services.news_signal_enrichment import EVENT_FAMILIES

STOCK = "엔비디아"
PARAMS = {"market": "미국", "limit": 50, "storyboard_limit": 3,
          "display_timezone": "Asia/Seoul"}

# Defensively fail if the builder unexpectedly attempts a snapshot write.
def reject_write(*args, **kwargs):
    raise RuntimeError("READ_ONLY_TEST_ATTEMPTED_DB_WRITE")
for operation in ("save_snapshot", "mark_checked", "purge_expired"):
    if hasattr(store, operation):
        setattr(store, operation, reject_write)

def emit(label, value):
    print(label + " " + json.dumps(value, ensure_ascii=False, default=str), flush=True)

def normalized(text):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(text or "").lower())

def duplicate_key(brief):
    events = brief.get("selected_events") or []
    if not events:
        return ("unique", str(brief.get("issue_id") or ""))
    event = events[0]
    kind = str(event.get("event_type") or "")
    status = str(event.get("status") or "")
    first = str(brief.get("_issue_first_published_at") or "")[:10]
    actor = normalized(event.get("actor"))
    reported = event.get("reported_numbers") or []
    if actor and reported:
        return ("structured", kind, status, first, actor,
                json.dumps(reported, ensure_ascii=False, sort_keys=True, default=str))
    sentence = normalized(event.get("evidence_sentence") or "")
    if sentence:
        return ("same_sentence", kind, status, first, sentence)
    return ("unique", str(brief.get("issue_id") or ""))

emit("TEST_SCOPE", {"stock": STOCK, "source": "LIVE_DIGITALOCEAN_NEWS_FETCH",
    "max_articles": 50, "max_age_hours": 24, "event_families": len(EVENT_FAMILIES),
    "dedupe": "exact_structured_fact_or_exact_evidence_sentence",
    "database_writes": False, "ai_calls": False, "deployment_changes": False})
if len(EVENT_FAMILIES) != 14 or len(set(EVENT_FAMILIES)) != 14:
    raise RuntimeError("LIVE_EVENT_TAXONOMY_NOT_14")
raw = news_feed.fetch_stock_news(STOCK, market="미국", limit=50,
                                 raise_on_error=True)
emit("COLLECTED", {"count": len(raw),
    "newest_title": str(raw[0].get("title") or "") if raw else ""})
if not raw:
    raise RuntimeError("NO_NVIDIA_NEWS_COLLECTED")
if len(raw) > 50:
    raise RuntimeError("COLLECTION_EXCEEDS_50")
result = build_stock_news_result(STOCK, raw_news_list=raw, **PARAMS)
if result.get("_news_status") != "ok":
    raise RuntimeError("LIVE_SELECTION_NOT_OK")
if result.get("_event_taxonomy_revision") != 1 or result.get("_issue_selection_revision") != 2:
    raise RuntimeError("LIVE_SELECTION_REVISION_MISMATCH")
articles = result.get("paired_news_items") or []
selected = result.get("issue_briefs") or []
rejected = result.get("_issue_selection_rejections") or []
raw_families = Counter()
for article in articles:
    for family in (article.get("event_classification") or {}).get("families") or []:
        raw_families[str(family)] += 1
emit("DIGITALOCEAN_NATIVE_SELECTION", {
    "collected": len(raw), "within_24h": len(articles),
    "with_14_family_event": sum(bool((a.get("event_classification") or {}).get("events")) for a in articles),
    "family_counts": dict(raw_families), "selected_issues": len(selected),
    "rejected_articles": len(rejected), "event_clusters_diagnostic_only":
        len(result.get("event_clusters") or [])})
unique = {}
merged = []
for brief in selected:
    key = duplicate_key(brief)
    if key in unique:
        first = unique[key]
        refs = first.setdefault("source_articles", [])
        known = {s.get("url") for s in refs}
        for source in brief.get("source_articles") or []:
            if source.get("url") not in known:
                refs.append(source)
                known.add(source.get("url"))
        merged.append({"duplicate": brief.get("headline"), "kept": first.get("headline"),
                       "reason": key[0]})
    else:
        unique[key] = {**brief,
            "source_articles": list(brief.get("source_articles") or [])}
final = list(unique.values())
emit("DEDUPLICATION", {"before": len(selected), "removed": len(merged),
    "after": len(final), "method": "conservative_exact_evidence_only"})
for i, brief in enumerate(final, 1):
    main = (brief.get("selected_events") or [{}])[0]
    emit("SELECTED_EVENT", {"rank": i, "headline": brief.get("headline"),
        "published_at": brief.get("_issue_first_published_at"),
        "family": main.get("family"), "event_type": main.get("event_type"),
        "source_urls": [s.get("url") for s in brief.get("source_articles") or []]})
for item in merged:
    emit("DUPLICATE_REMOVED", item)
emit("LATEST_THREE", [
    {"headline": b.get("headline"), "published_at": b.get("_issue_first_published_at")}
    for b in final[:3]])
print("NVIDIA_14_FAMILY_READ_ONLY_TEST_COMPLETE", flush=True)
