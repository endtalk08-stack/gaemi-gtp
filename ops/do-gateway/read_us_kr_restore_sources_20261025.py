"""Read-only in-memory preflight of US-only KR selection restoration."""
from pathlib import Path
import hashlib

base = Path("/opt/gaemigtp-news/app/backend/services")
src = (base/"news_result.py").read_text()
store = (base/"news_processed_store.py").read_text()
sha = lambda v: hashlib.sha256(v.encode("utf-8")).hexdigest()
assert sha(src) == "294aa00b46bbcb64602f9d05f619af1911fe83018d0cd1a81d2d8da9efb36d0d", "RESULT_LIVE_DRIFT_STOP"
assert sha(store) == "878c658c84072dd9046464ae6b8bf67174a69f6da5ad84fb7b2cdded72163618", "STORE_LIVE_DRIFT_STOP"

def replace_once(text, before, after, label):
    if text.count(before) != 1:
        raise AssertionError("PATCH_ANCHOR_MISMATCH_" + label)
    return text.replace(before, after, 1)

src = replace_once(
    src, "from .news_feed import fetch_stock_news\n",
    "from .news_feed import fetch_stock_news, select_stock_news_for_analysis\n",
    "DOMESTIC_SELECTOR_IMPORT")
src = replace_once(
    src,
    "        part_started = time.monotonic()\n        scored_news = score_stock_news(raw_news_list, stock_name)\n",
    "        # US CODE only: same article/keyword eligibility already used by KR.\n"
    "        # Keep the raw news list unchanged for its independent consumers.\n"
    "        code_news = (\n"
    "            select_stock_news_for_analysis(raw_news_list, stock_name, limit)\n"
    "            if market in (\"미국\", \"US\", \"us\") else raw_news_list\n"
    "        )\n"
    "        part_started = time.monotonic()\n"
    "        scored_news = score_stock_news(code_news, stock_name)\n",
    "US_CODE_INPUT")
src = replace_once(
    src,
    "            limit = max(12, len(rows)) if market in (\"미국\", \"US\", \"us\") else max(12, storyboard_limit * 3)",
    "            limit = max(12, storyboard_limit * 3)",
    "KR_CANDIDATE_LIMIT")
src = replace_once(
    src,
    "        issue_count_limit = max(1, len(candidate_news)) if is_us_24h else storyboard_limit",
    "        issue_count_limit = storyboard_limit",
    "KR_ISSUE_COUNT")
src = replace_once(
    src,
    "                if market not in (\"미국\", \"US\", \"us\") and not central_material_brief_supported(excerpt):",
    "                if not central_material_brief_supported(excerpt):",
    "KR_MATERIAL_GATE")
suffix = (
    "        # US only: drop redundant trailing issue label. Keep sources and content.\n"
    "        if market in (\"미국\", \"US\", \"us\"):\n"
    "            for brief in issue_briefs:\n"
    "                if isinstance(brief, dict):\n"
    "                    brief[\"headline\"] = re.sub(r\"\\s*이슈\\s*$\", \"\", str(brief.get(\"headline\") or \"\").strip()).strip()\n"
    "\n"
)
src = replace_once(src, suffix, "", "KEEP_KR_KEYWORD_TITLE")
src = replace_once(
    src, "\"_code_source_revision\": 13 if market in (\"미국\", \"US\", \"us\") else None",
    "\"_code_source_revision\": 14 if market in (\"미국\", \"US\", \"us\") else None",
    "CODE_CACHE_REFRESH")
store = replace_once(
    store, "payload.get(\"_code_source_revision\") != 13",
    "payload.get(\"_code_source_revision\") != 14",
    "CODE_CACHE_SIGNATURE")

for filename, value in (("news_result.py", src), ("news_processed_store.py", store)):
    compile(value, filename, "exec")
assert src.count("attach_verified_source_citations(") == 1
assert 'if not is_us_24h:\n            candidate_news.extend(rank_candidates(older_news))' in src
assert 'if market in ("미국", "US", "us"):' in src
assert src.count("limit=issue_count_limit") == 2
assert '"_code_source_revision": 14' in src
assert 'payload.get("_kr_selection_revision") != 1' in store
assert 'def _same_stock_issue_briefs' in store
assert 'def _prefer_same_day_ai' in store
assert 'def _recent_existing_issue_briefs' in store
from backend.services.news_feed import select_stock_news_for_analysis
from backend.services.issue_briefs import _content_driven_title_and_tags
assert callable(select_stock_news_for_analysis)
assert callable(_content_driven_title_and_tags)
print("US_KR_READONLY_PREFLIGHT_PASS")
print("NEW_RESULT_SHA256", sha(src))
print("NEW_STORE_SHA256", sha(store))
print("PROTECTED_SOURCE_AND_STORE_BEHAVIOR_PRESERVED")
