"""Read-only TradingView news preflight; no network, writes, or service control."""
import datetime as dt
import json
import os
import pathlib
import subprocess

def unit(name):
    try:
        p = subprocess.run(["systemctl", "is-active", name], capture_output=True,
                           text=True, timeout=5, check=False)
        return p.stdout.strip()[:32] or "unknown"
    except Exception as exc:
        return "error:" + type(exc).__name__

units = ["gaemigtp-news.service", "gaemigtp-tradingview-news.service",
         "gaemigtp-tradingview-news.timer",
         "gaemigtp-us-market-close.service", "gaemigtp-us-market-close.timer"]
states = {name: unit(name) for name in units}
cache = {}
for label, location in (
    ("overall_cache", "/var/lib/gaemigtp-news/tradingview-news-bundle.json"),
    ("stock_cache", "/var/lib/gaemigtp-news/tradingview-us-stock-news.json"),
):
    p = pathlib.Path(location)
    if p.is_symlink():
        cache[label] = {"status": "symlink_blocked"}
        continue
    try:
        if p.stat().st_size > 10_000_000:
            cache[label] = {"status": "too_large"}
            continue
        state = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            cache[label] = {"status": "unexpected_format"}
            continue
        cache[label] = {
            "status": "ok",
            "mode": str(state.get("mode", "unknown"))[:32],
            "items": len(state.get("items", [])) if isinstance(state.get("items"), list) else None,
            "local_requests_total": state.get("requests_total", state.get("requests")),
            "local_month": state.get("month", state.get("four_feed_month")),
            "local_four_feed_month_requests": state.get("four_feed_month_requests"),
            "last_attempt": state.get("last_attempt"),
        }
    except FileNotFoundError:
        cache[label] = {"status": "not_found"}
    except (OSError, ValueError, TypeError) as exc:
        cache[label] = {"status": "error:" + type(exc).__name__}

now = dt.datetime.now(dt.timezone.utc)
result = {
    "kind": "tv_news_preflight_readonly",
    "timestamp_utc": now.isoformat(),
    "api_key_present": bool(os.environ.get("TRADINGVIEW_API_KEY", "").strip()),
    "news_mode": str(os.environ.get("TRADINGVIEW_NEWS_MODE", "unset"))[:30],
    "four_feeds_flag": os.environ.get("TRADINGVIEW_NEWS_FOUR_FEEDS_ENABLED", "unset") == "1",
    "local_month": now.strftime("%Y-%m"),
    "units": states,
    "cache": cache,
    "provider_remaining_quota": "not_available_from_local_cache",
    "network_calls": 0,
}
print("TV_PREFLIGHT_RESULT=" + json.dumps(result, ensure_ascii=False, separators=(",", ":")), flush=True)
if states["gaemigtp-news.service"] == "active" or states["gaemigtp-tradingview-news.service"] == "active":
    raise SystemExit("TV_PREFLIGHT_STOP_WORKER_RUNNING")
print("TV_PREFLIGHT_DONE_ZERO_API_CALLS", flush=True)
