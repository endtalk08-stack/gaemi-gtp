"""Read-only pre-collection verification. No API, DB, R2, or service writes."""
from __future__ import annotations

import hashlib
import pathlib
import subprocess

BASE = pathlib.Path("/opt/gaemigtp-news/app")
FILES = (
    "backend/providers/tradingview_news_bundle.py",
    "backend/services/tradingview_news_page.py",
    "backend/providers/tradingview_news_detail.py",
    "backend/tradingview_news_worker.py",
    "backend/services/r2_news_uploader.py",
)
def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

print("NEWS_PRECOLLECTION_INSPECT_READONLY=1", flush=True)
for rel in FILES:
    path = BASE / rel
    if not path.is_file() or path.is_symlink():
        print("FILE=" + rel + " STATUS=missing", flush=True)
        continue
    data = path.read_bytes()
    print("FILE=" + rel + " GIT_BLOB_SHA=" + git_blob_sha(data) + " SIZE=" + str(len(data)), flush=True)
    if rel.endswith("tradingview_news_bundle.py"):
        text = data.decode("utf-8", "replace")
        print("BUNDLE_OVERALL_ONLY=" + str('categories = ("overall",)' in text and 'four_enabled = False' in text), flush=True)
    if rel.endswith("tradingview_news_worker.py"):
        text = data.decode("utf-8", "replace")
        print("DETAIL_AUTOMATIC=" + str("enrich_articles(" in text), flush=True)
for unit in ("gaemigtp-news.service", "gaemigtp-tradingview-news.service"):
    p = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=10)
    print("UNIT=" + unit + " STATE=" + p.stdout.strip(), flush=True)
print("NEWS_PRECOLLECTION_INSPECT_COMPLETE=1", flush=True)
