"""Read-only readiness check for existing US TOP20 news R2 migration.

No API requests, no secret values, no database calls, no service control.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

ROOT = Path("/var/lib/gaemigtp-news")
RANKING = ROOT / "kiwoom-us-top20-news.json"
ROTATION = ROOT / "rotation.json"
SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z")
now = dt.datetime.now(dt.timezone.utc)

print("TOP20_READONLY_BEGIN=1")
print("CHECKED_AT_UTC=" + now.isoformat())
for name, path in (("ranking", RANKING), ("rotation", ROTATION)):
    print(name.upper() + "_EXISTS=" + str(path.is_file()))
    print(name.upper() + "_SYMLINK=" + str(path.is_symlink()))
    if not path.is_file() or path.is_symlink():
        continue
    try:
        st = path.stat()
        print(name.upper() + "_MTIME_UTC=" + dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).isoformat())
        print(name.upper() + "_AGE_HOURS=" + str(round((now.timestamp() - st.st_mtime)/3600, 2)))
        print(name.upper() + "_SIZE_BYTES=" + str(st.st_size))
        if st.st_size > 1024 * 1024:
            print(name.upper() + "_STATUS=too_large")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            print(name.upper() + "_STATUS=invalid_object")
            continue
        if name == "ranking":
            print("RANKING_SCHEMA_VERSION=" + str(data.get("schema_version")))
            print("RANKING_SOURCE=" + str(data.get("source")))
            print("RANKING_MARKET=" + str(data.get("market")))
            print("RANKING_RANK_TYPE=" + str(data.get("rank_type")))
            rows = data.get("items")
            rows = rows if isinstance(rows, list) else []
            symbols = [str(r.get("symbol") or "") for r in rows if isinstance(r, dict)]
            valid = len(rows) == 20 and len(symbols) == 20 and len(set(symbols)) == 20 and all(SYMBOL.fullmatch(s) for s in symbols)
            print("RANKING_ITEMS=" + str(len(rows)))
            print("RANKING_UNIQUE_SYMBOLS=" + str(len(set(symbols))))
            print("RANKING_VALID_SHAPE=" + str(bool(valid)))
            print("RANKING_STOCK_NAMES_PRESENT=" + str(sum(bool(str(r.get("name") or "").strip()) for r in rows if isinstance(r, dict))))
            print("RANKING_EXPECTED_METADATA=" + str(all((data.get("schema_version")==1,data.get("source")=="kiwoom",data.get("market")=="US",data.get("rank_type")=="trading_value"))))
            # Do not publish the rankings themselves; avoid sensitive or noisy log data.
            for key in ("generated_at", "updated_at", "collected_at", "as_of"):
                if key in data:
                    print("RANKING_" + key.upper() + "=" + str(data[key])[:80])
        else:
            cycle = data.get("cycle")
            print("ROTATION_CYCLE_PRESENT=" + str(bool(cycle)))
            print("ROTATION_NEXT_INDEX=" + str(data.get("next_index")))
            print("ROTATION_BATCH_PROGRESS=" + str(data.get("_batch_progress")))
            print("ROTATION_FINGERPRINT_COUNT=" + str(len(data.get("_r2_news_fingerprints") or {})))
            print("ROTATION_AI_RESERVATIONS=" + str(len(data.get("_r2_ai_reservations") or {})))
        print(name.upper() + "_STATUS=read_ok")
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        print(name.upper() + "_STATUS=" + type(exc).__name__)

for key in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "GROQ_API_KEY",
            "GAEMIGTP_NEWS_STORAGE", "GAEMIGTP_NEWS_AI_PAUSED",
            "GAEMIGTP_NEWS_AI_R2_ENABLED"):
    if key == "GAEMIGTP_NEWS_STORAGE":
        print("CONFIG_" + key + "=" + os.getenv(key, "not_set"))
    else:
        print("CONFIG_" + key + "_SET=" + str(bool(os.getenv(key, "").strip())))
print("TOP20_READONLY_END=1")
