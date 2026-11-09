"""Single-stock existing TOP20 news -> R2 probe. No rotation-state writes or AI."""
from __future__ import annotations
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("/opt/gaemigtp-news/app")
R2_ENV = Path("/var/lib/gaemigtp-news/r2.env")
STATE = Path("/var/lib/gaemigtp-news/rotation.json")
sys.path.insert(0, str(ROOT))

def state_of(unit, prop):
    return subprocess.run(
        ["systemctl", "show", unit, "--property=" + prop, "--value"],
        check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip()

def abort(reason):
    raise SystemExit("TOP20_SINGLE_PROBE_ABORT=" + reason)

if (state_of("gaemigtp-news.service", "ActiveState") != "inactive"
    or state_of("gaemigtp-news.service", "UnitFileState") != "disabled"):
    abort("NEWS_SERVICE_MUST_REMAIN_STOPPED")
if state_of("gaemigtp-tradingview-news.service", "ActiveState") != "active":
    abort("TRADINGVIEW_MUST_REMAIN_ACTIVE")
if not R2_ENV.is_file() or R2_ENV.is_symlink() or R2_ENV.stat().st_mode & 0o777 != 0o600:
    abort("R2_ENV_NOT_SAFE")
if not STATE.is_file() or STATE.is_symlink():
    abort("ROTATION_STATE_NOT_REGULAR_FILE")
for line in R2_ENV.read_text(encoding="utf-8").splitlines():
    key, sep, value = line.partition("=")
    if sep and key in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "GAEMIGTP_NEWS_STORAGE"):
        os.environ[key] = value.strip()
if (os.environ.get("GAEMIGTP_NEWS_STORAGE") != "r2"
    or not os.environ.get("R2_ACCESS_KEY_ID") or not os.environ.get("R2_SECRET_ACCESS_KEY")):
    abort("R2_SETTINGS_INCOMPLETE")
# Do not allow this probe to connect to Neon or invoke any paid AI model.
for key in ("NEWS_DATABASE_URL", "DATABASE_URL", "GROQ_API_KEY"):
    os.environ.pop(key, None)
os.environ.update({
    "GAEMIGTP_NEWS_STORAGE": "r2",
    "GAEMIGTP_NEWS_AI_PAUSED": "1",
    "GAEMIGTP_NEWS_AI_R2_ENABLED": "0",
    "GAEMIGTP_NEWS_WORKER": "1",
})

import json
from backend.news_worker import process_r2_stock
from backend.services.news_r2_ai import enabled
from backend.services.us_top20_rotation import normalize_ranking

if enabled():
    abort("AI_MUST_BE_DISABLED")
state = json.loads(STATE.read_text(encoding="utf-8"))
cycle = normalize_ranking(state.get("cycle"))
if len(cycle) != 20:
    abort("NO_VALID_FROZEN_TOP20")
item = cycle[0]
symbol = str(item["symbol"])
name = str(item["name"])
if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", symbol):
    abort("INVALID_SYMBOL")
print("TOP20_SINGLE_PROBE_SOURCE=EXISTING_FROZEN_RANKING_NOT_CURRENT")
print("TOP20_SINGLE_PROBE_SYMBOL=" + symbol)
print("TOP20_SINGLE_PROBE_RANK=" + str(item["rank"]))
print("TOP20_SINGLE_PROBE_NEON_DISABLED=True")
print("TOP20_SINGLE_PROBE_AI_PAUSED=True")
print("TOP20_SINGLE_PROBE_ROTATION_NOT_MODIFIED=True")
print("TOP20_SINGLE_PROBE_TARGET=news/stocks/us/" + symbol + ".json")
# A fresh in-memory state means neither persistent rotation nor AI reservations are changed.
result = process_r2_stock("미국", name, symbol, {})
if result != "updated":
    abort("UNEXPECTED_RESULT_" + str(result))
print("TOP20_SINGLE_PROBE_R2_UPLOAD_SUCCESS=True")
if state_of("gaemigtp-news.service", "ActiveState") != "inactive":
    abort("NEWS_SERVICE_STATE_CHANGED")
print("TOP20_SINGLE_PROBE_NEWS_STILL_STOPPED=True")
