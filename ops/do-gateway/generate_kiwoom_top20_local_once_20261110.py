"""One-shot existing Kiwoom USA20540 ranking -> validated local TOP20 JSON, no Neon."""
from __future__ import annotations
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path("/opt/gaemigtp-news/app")
TARGET=Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
sys.path.insert(0,str(ROOT))

def prop(unit,key):
    return subprocess.run(["systemctl","show",unit,"--property="+key,"--value"],
      capture_output=True,text=True,check=True,timeout=10).stdout.strip()

if prop("gaemigtp-news.service","ActiveState")!="inactive":
    raise SystemExit("KIWOOM_LOCAL_ABORT_NEWS_MUST_STAY_STOPPED")
if prop("gaemigtp-tradingview-news.service","ActiveState")!="active":
    raise SystemExit("KIWOOM_LOCAL_ABORT_TRADINGVIEW_NOT_ACTIVE")
if TARGET.is_symlink() or not TARGET.parent.is_dir():
    raise SystemExit("KIWOOM_LOCAL_ABORT_UNSAFE_DESTINATION")
print("KIWOOM_LOCAL_EXISTED_BEFORE="+str(TARGET.is_file()),flush=True)
print("KIWOOM_LOCAL_APP_KEY_PRESENT="+str(bool(os.environ.get("GAEMI_KIWOOM_APP_KEY","").strip())),flush=True)
print("KIWOOM_LOCAL_APP_SECRET_PRESENT="+str(bool(os.environ.get("GAEMI_KIWOOM_APP_SECRET","").strip())),flush=True)
if not (os.environ.get("GAEMI_KIWOOM_APP_KEY","").strip()
        and os.environ.get("GAEMI_KIWOOM_APP_SECRET","").strip()):
    raise SystemExit("KIWOOM_LOCAL_ABORT_NO_EXISTING_KIWOOM_CREDENTIALS")
for key in ("NEWS_DATABASE_URL","DATABASE_URL","GROQ_API_KEY"):
    os.environ.pop(key,None)
os.environ["GAEMIGTP_NEWS_AI_PAUSED"]="1"
os.environ["GAEMIGTP_NEWS_AI_R2_ENABLED"]="0"
print("KIWOOM_LOCAL_NEON_AI_DISABLED=True",flush=True)

from backend import kiwoom_us_value_collector as collector
from backend.services.us_top20_rotation import normalize_ranking
from backend.kiwoom_us_identity_sync import identity_from_kiwoom
start=dt.datetime.now(dt.timezone.utc)
sys.argv=["kiwoom_us_value_collector.py","--local-news-top20"]
try:
    rc=collector.main()
except Exception as exc:
    print("KIWOOM_LOCAL_PROVIDER_ERROR="+type(exc).__name__,flush=True)
    raise SystemExit(1) from None
if rc!=0:
    raise SystemExit("KIWOOM_LOCAL_COLLECTOR_EXIT="+str(rc))
if not TARGET.is_file() or TARGET.is_symlink():
    raise SystemExit("KIWOOM_LOCAL_NO_OUTPUT")
data=json.loads(TARGET.read_text(encoding="utf-8"))
expected={"schema_version":1,"source":"kiwoom","market":"US","rank_type":"trading_value"}
if any(data.get(k)!=v for k,v in expected.items()):
    raise SystemExit("KIWOOM_LOCAL_INVALID_HEADER")
rows=normalize_ranking(data.get("items"))
if len(rows)!=20:
    raise SystemExit("KIWOOM_LOCAL_INVALID_ROWS")
for row,original in zip(rows,data["items"]):
    ident=identity_from_kiwoom(row["name"],row["symbol"])
    if not ident or any(original.get(k)!=ident[v] for k,v in
        (("company_key","company_key"),("news_name","news_name"),
         ("identity_status","status"))):
        raise SystemExit("KIWOOM_LOCAL_INVALID_IDENTITY")
captured=dt.datetime.fromisoformat(data["captured_at"])
if captured.tzinfo is None or captured < start-dt.timedelta(seconds=3):
    raise SystemExit("KIWOOM_LOCAL_NOT_FRESH")
print("KIWOOM_LOCAL_RANK_ITEMS="+str(len(rows)),flush=True)
print("KIWOOM_LOCAL_CAPTURED_UTC="+data["captured_at"],flush=True)
print("KIWOOM_LOCAL_FILE_MODE="+oct(TARGET.stat().st_mode & 0o777),flush=True)
print("KIWOOM_LOCAL_DATA_VERIFIED=True",flush=True)
print("KIWOOM_LOCAL_NEWS_STILL_STOPPED="+str(prop("gaemigtp-news.service","ActiveState")=="inactive"),flush=True)
print("KIWOOM_LOCAL_TRADINGVIEW_STILL_ACTIVE="+str(prop("gaemigtp-tradingview-news.service","ActiveState")=="active"),flush=True)
