"""Rebuild the existing R2 news snapshot from local cache; zero API calls."""
import fcntl
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers.tradingview_news_bundle import CACHE_PATH
from backend.services.tradingview_news_page import NEWS_PAGE_PATH, write_snapshot
from backend.services.r2_news_uploader import upload_file


def main():
    if not CACHE_PATH.is_file() or CACHE_PATH.is_symlink():
        raise SystemExit("NEWS_CACHE_MISSING")
    lock_path = CACHE_PATH.with_suffix(".lock")
    if lock_path.is_symlink():
        raise SystemExit("UNSAFE_CACHE_LOCK")
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
        state = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        articles = state.get("items")
        if not isinstance(articles, list):
            raise SystemExit("INVALID_CACHE_ITEMS")
        snapshot = write_snapshot(articles)
    env_path = Path("/var/lib/gaemigtp-news/r2.env")
    if not env_path.is_file():
        raise SystemExit("R2_ENV_MISSING")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"}:
            os.environ[key] = value
    if not upload_file(NEWS_PAGE_PATH):
        raise SystemExit("R2_UPLOAD_FAILED")
    rows = snapshot["items"]
    print("NEWS_SNAPSHOT_REPUBLISHED=" + json.dumps({
        "total": len(rows),
        "summaries": sum(bool(x.get("summary")) for x in rows),
        "descriptions": sum(bool(x.get("description")) for x in rows),
        "publishable_bodies": sum(bool(x.get("body")) for x in rows),
    }), flush=True)


if __name__ == "__main__":
    main()
