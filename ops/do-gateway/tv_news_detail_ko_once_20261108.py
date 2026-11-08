"""Publish existing one-time top-article detail from local cache to existing R2, without API calls."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers.tradingview_news_bundle import CACHE_PATH
from backend.services.tradingview_news_page import NEWS_PAGE_PATH
from backend.services.r2_news_uploader import upload_file

for u in ("gaemigtp-news.service","gaemigtp-tradingview-news.service"):
    p=subprocess.run(("systemctl","is-active",u),capture_output=True,text=True,timeout=8)
    if p.stdout.strip()!="inactive":
        raise SystemExit("STOP_WORKER_ACTIVE")
target_id="tag:reuters.com,2026:newsml_L3N46P01F:0"
expected_title="파이낸셜 타임스(FT) 보도에 따르면, 앤트로픽이 데이터센터용 발전기 공급 계약을 34억 달러에 체결했다"
if not CACHE_PATH.is_file() or CACHE_PATH.is_symlink() or not NEWS_PAGE_PATH.is_file() or NEWS_PAGE_PATH.is_symlink():
    raise SystemExit("STOP_MISSING_LOCAL_STATE")
state=json.loads(CACHE_PATH.read_text(encoding="utf-8"))
matches=[x for x in state.get("items",[]) if isinstance(x,dict) and x.get("id")==target_id]
if len(matches)!=1:
    raise SystemExit("STOP_NO_EXACT_CACHE_ARTICLE")
body=matches[0].get("detail_body") or ""
if len(body)!=606:
    raise SystemExit("STOP_CACHED_BODY_NOT_606")
snapshot=json.loads(NEWS_PAGE_PATH.read_text(encoding="utf-8"))
if snapshot.get("count")!=26 or len(snapshot.get("items",[]))!=26:
    raise SystemExit("STOP_SNAPSHOT_COUNT_MISMATCH")
top=snapshot["items"][0]
if top.get("id")!=target_id or top.get("title")!=expected_title:
    raise SystemExit("STOP_TOP_ARTICLE_MISMATCH")
if any((x.get("body") or "") for x in snapshot["items"][1:]):
    raise SystemExit("STOP_OTHER_ARTICLE_BODY_CHANGED")
top["body"]=body
top["body_available"]=True
top["detail_status"]="content"
# Preserve all other entries byte-for-byte in content; update only first article fields.
fd,tmp=tempfile.mkstemp(prefix=".tv-news-body-",dir=str(NEWS_PAGE_PATH.parent))
try:
    os.fchmod(fd,0o600)
    with os.fdopen(fd,"w",encoding="utf-8") as out:
        json.dump(snapshot,out,ensure_ascii=False,separators=(",",":"))
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp,NEWS_PAGE_PATH)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)
env_path=Path("/var/lib/gaemigtp-news/r2.env")
if not env_path.is_file() or env_path.is_symlink():
    raise SystemExit("STOP_R2_ENV_MISSING")
for line in env_path.read_text(encoding="utf-8").splitlines():
    if "=" in line:
        key,value=line.split("=",1)
        if key in ("R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY"):
            os.environ[key]=value
if not upload_file(NEWS_PAGE_PATH):
    raise SystemExit("STOP_R2_UPLOAD_FAILED")
print("TV_TOP1_R2_PUBLISHED=1 ARTICLE_COUNT=26 BODY_CHARS=606 API_CALLS=0",flush=True)
