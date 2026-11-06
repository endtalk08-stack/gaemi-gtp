"""Collect details for cached non-headline news only, without touching the other 199 items."""
import fcntl
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers.tradingview_news_bundle import CACHE_PATH, _write
from backend.providers.tradingview_news_detail import enrich_articles
from backend.services.tradingview_news_page import NEWS_PAGE_PATH, write_snapshot
from backend.services.r2_news_uploader import upload_file

def main():
    if not os.getenv("TRADINGVIEW_API_KEY", "").strip():
        raise SystemExit("API_KEY_MISSING")
    lock_path=CACHE_PATH.with_suffix(".lock")
    if CACHE_PATH.is_symlink() or lock_path.is_symlink():
        raise SystemExit("UNSAFE_CACHE")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state=json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        items=state.get("items",[])
        choices=[(i,row) for i,row in enumerate(items) if isinstance(row,dict) and row.get("permission")!="headline" and not row.get("detail_checked")]
        if not choices:
            print("NEWS_NONHEADLINE_NOTHING_TO_CHECK", flush=True)
            return
        updated,stats=enrich_articles([row for _,row in choices],max_requests=len(choices))
        for (i,_),row in zip(choices,updated):
            items[i]=row
        print("NEWS_NONHEADLINE_STATS="+json.dumps({"eligible":len(choices),**stats}), flush=True)
        if not stats["requested"]:
            return
        state["items"]=items
        _write(state)
        snap=write_snapshot(items)
    env=Path("/var/lib/gaemigtp-news/r2.env")
    if not env.is_file(): raise SystemExit("R2_ENV_MISSING")
    for line in env.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k,v=line.split("=",1)
            if k in {"R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY"}:
                os.environ[k]=v
    if not upload_file(NEWS_PAGE_PATH):
        raise SystemExit("R2_UPLOAD_FAILED")
    print("NEWS_NONHEADLINE_R2_ITEMS="+str(snap["count"]),flush=True)

if __name__=="__main__":
    main()
