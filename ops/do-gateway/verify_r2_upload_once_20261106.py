from __future__ import annotations
import os
import sys
from pathlib import Path

app = Path("/opt/gaemigtp-news/app")
sys.path.insert(0, str(app))
env_path = Path("/var/lib/gaemigtp-news/r2.env")
snapshot = Path("/var/lib/gaemigtp-news/tradingview-news-page.json")
if not env_path.is_file():
    raise SystemExit("R2_ENV_MISSING")
for raw in env_path.read_text(encoding="utf-8").splitlines():
    if raw and "=" in raw:
        k, v = raw.split("=", 1)
        if k in {"R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"}:
            os.environ[k] = v
from backend.services.r2_news_uploader import upload_file
ok = upload_file(snapshot)
if not ok:
    raise SystemExit("R2_UPLOAD_VERIFY_FAILED")
print("R2_UPLOAD_VERIFY_OK")
