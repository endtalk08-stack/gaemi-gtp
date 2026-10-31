"""Single live TradingView API response test. No DB, AI, cache writes, or worker start."""
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

APP = "/opt/gaemigtp-news/app"
if APP not in sys.path:
    sys.path.insert(0, APP)

def worker_state():
    p = subprocess.run(["systemctl", "is-active", "gaemigtp-news.service"],
                       capture_output=True, text=True, timeout=10)
    return p.stdout.strip()

assert worker_state() == "inactive", "news_worker_must_remain_inactive"
key = os.environ.get("TRADINGVIEW_API_KEY", "").strip()
assert key, "TRADINGVIEW_API_KEY_NOT_AVAILABLE_TO_GATEWAY"

request = urllib.request.Request(
    "https://api.tradingviewapi.com/api/news/stock",
    headers={"Authorization": "Bearer " + key,
             "Accept": "application/json",
             "User-Agent": "gaemiGTP-news-api-check/1.0"},
    method="GET",
)
try:
    with urllib.request.urlopen(request, timeout=15) as response:
        status = response.status
        content_type = response.headers.get("Content-Type", "")
        raw = response.read(2_000_000)
except Exception as exc:
    print("TV_HTTP_ERROR", type(exc).__name__, flush=True)
    raise SystemExit(2)

print("TV_HTTP_STATUS", status, flush=True)
print("TV_CONTENT_TYPE", content_type, flush=True)
print("TV_RESPONSE_BYTES", len(raw), flush=True)
try:
    payload = json.loads(raw.decode("utf-8"))
except Exception as exc:
    print("TV_JSON_PARSE_ERROR", type(exc).__name__, flush=True)
    print("TV_BODY_PREFIX", raw[:300].decode("utf-8", "replace"), flush=True)
    raise SystemExit(3)

print("TV_TOP_LEVEL_TYPE", type(payload).__name__, flush=True)
if isinstance(payload, dict):
    print("TV_TOP_LEVEL_KEYS", sorted(str(k) for k in payload.keys()), flush=True)
elif isinstance(payload, list):
    print("TV_TOP_LEVEL_COUNT", len(payload), flush=True)

def inspect(value, path="$", depth=0):
    if depth > 4:
        return
    if isinstance(value, dict):
        print("TV_OBJECT", path, "KEYS", sorted(str(k) for k in value.keys())[:80], flush=True)
        # Expose only non-secret article metadata needed to implement the adapter.
        for k in ("title", "headline", "link", "url", "storyPath", "published",
                  "publishedAt", "provider", "source", "relatedSymbols", "symbols",
                  "symbol", "id"):
            if k in value:
                v = value[k]
                if isinstance(v, (str, int, float, bool)) or v is None:
                    print("TV_FIELD", path + "." + k, repr(v)[:500], flush=True)
                elif isinstance(v, list):
                    print("TV_FIELD", path + "." + k, "LIST_COUNT", len(v), flush=True)
                    if v and isinstance(v[0], dict):
                        print("TV_FIELD_OBJECT_KEYS", path + "." + k, sorted(v[0].keys())[:60], flush=True)
        for k, v in value.items():
            if isinstance(v, (dict, list)):
                inspect(v, path + "." + str(k), depth + 1)
    elif isinstance(value, list):
        print("TV_ARRAY", path, "COUNT", len(value), flush=True)
        if value:
            inspect(value[0], path + "[0]", depth + 1)

inspect(payload)
assert worker_state() == "inactive", "news_worker_state_changed"
print("TV_API_ONE_CALL_TEST_COMPLETE_WORKER_STILL_INACTIVE", flush=True)
