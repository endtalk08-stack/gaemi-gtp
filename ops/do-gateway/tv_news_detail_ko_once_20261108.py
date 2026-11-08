"""One authorized TradingView top-story detail request and R2 display, no list calls."""
import fcntl
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers.tradingview_news_bundle import CACHE_PATH, _write
from backend.providers.tradingview_news_detail import _get_detail, _extract_detail, DETAIL_PARSER_VERSION
from backend.services.tradingview_news_page import NEWS_PAGE_PATH, build_snapshot, write_snapshot
from backend.services.r2_news_uploader import upload_file

UNITS = ("gaemigtp-news.service", "gaemigtp-tradingview-news.service")
def inactive(unit):
    p = subprocess.run(("systemctl", "is-active", unit), text=True, capture_output=True, timeout=8)
    return p.stdout.strip() == "inactive"
if not all(inactive(u) for u in UNITS):
    raise SystemExit("STOP_WORKER_RUNNING")
target_id = "tag:reuters.com,2026:newsml_L3N46P01F:0"
expected_title = "파이낸셜 타임스(FT) 보도에 따르면, 앤트로픽이 데이터센터용 발전기 공급 계약을 34억 달러에 체결했다"
key = os.environ.get("TRADINGVIEW_API_KEY", "").strip()
if not key:
    raise SystemExit("STOP_NO_TV_KEY")
if not NEWS_PAGE_PATH.is_file() or NEWS_PAGE_PATH.is_symlink():
    raise SystemExit("STOP_SNAPSHOT_MISSING")
current = json.loads(NEWS_PAGE_PATH.read_text(encoding="utf-8"))
if (current.get("count") != 26 or not current.get("items") or
    current["items"][0].get("id") != target_id or
    current["items"][0].get("title") != expected_title):
    raise SystemExit("STOP_TOP_ARTICLE_MISMATCH")
if not CACHE_PATH.is_file() or CACHE_PATH.is_symlink():
    raise SystemExit("STOP_CACHE_MISSING")
lock_path = CACHE_PATH.with_suffix(".lock")
if lock_path.is_symlink():
    raise SystemExit("STOP_LOCK_SYMLINK")
r2_env = Path("/var/lib/gaemigtp-news/r2.env")
if not r2_env.is_file() or r2_env.is_symlink():
    raise SystemExit("STOP_R2_ENV_MISSING")
for line in r2_env.read_text(encoding="utf-8").splitlines():
    if "=" in line:
        k,v = line.split("=",1)
        if k in {"R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"}:
            os.environ[k] = v
if not os.environ.get("R2_ACCESS_KEY_ID") or not os.environ.get("R2_SECRET_ACCESS_KEY"):
    raise SystemExit("STOP_R2_KEY_MISSING")

print("TV_TOP1_DETAIL_API_REQUESTS=1 LIST_REQUESTS=0", flush=True)
try:
    detail = _get_detail(target_id, key, urllib.request.urlopen)
except urllib.error.HTTPError as e:
    print("TV_TOP1_DETAIL_HTTP_ERROR=" + str(e.code) + " NO_RETRY",flush=True)
    raise SystemExit(2)
except Exception as e:
    print("TV_TOP1_DETAIL_ERROR=" + type(e).__name__ + " NO_RETRY",flush=True)
    raise SystemExit(2)
content = _extract_detail(detail)["detail_body"]
if not content or len(content) < 100 or len(re.findall("[가-힣]", content)) < 50:
    raise SystemExit("STOP_DETAIL_CONTENT_INVALID")
print("TV_TOP1_EXTRACT_OK chars=" + str(len(content)) + " lang=" + str(detail.get("language")) +
      " permission=" + str(detail.get("permission")),flush=True)
if not all(inactive(u) for u in UNITS):
    raise SystemExit("STOP_WORKER_STATE_CHANGED")
# Preserve the local source cache so the top article survives a later snapshot republish.
with lock_path.open("a+",encoding="utf-8") as lock:
    fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
    state = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    rows = state.get("items", [])
    matches = [a for a in rows if isinstance(a,dict) and a.get("id") == target_id]
    if len(matches) != 1:
        raise SystemExit("STOP_CACHE_TARGET_MISSING_OR_DUPLICATE")
    item = matches[0]
    item["detail_body"] = content
    item["detail_checked"] = "content"
    item["detail_permission"] = detail.get("permission")
    item["detail_parser_version"] = DETAIL_PARSER_VERSION
    item["detail_publication_allowed"] = True
    item["detail_rights_confirmed"] = True
    proposed = build_snapshot(rows)
    if proposed.get("count") != 26 or proposed["items"][0].get("id") != target_id:
        raise SystemExit("STOP_GENERATED_SNAPSHOT_CHANGED")
    # Check the only public diff is the first article's detail fields.
    old = current["items"]; new = proposed["items"]
    if len(old)!=len(new) or any(a!=b for a,b in zip(old[1:],new[1:])):
        raise SystemExit("STOP_OTHER_ARTICLES_CHANGED")
    _write(state)
    saved = write_snapshot(rows)
    if saved["items"][0].get("body") != content:
        raise SystemExit("STOP_BODY_NOT_PUBLISHED_IN_SNAPSHOT")
if not upload_file(NEWS_PAGE_PATH):
    raise SystemExit("STOP_R2_UPLOAD_FAILED")
print("TV_TOP1_PUBLISHED=1 BODY_CHARS=" + str(len(content)) +
      " NEWS_ITEMS=26 OTHER_ARTICLES_UNCHANGED=1",flush=True)
