"""Opt-in Neon-free AI issue publication for existing US TOP20 news.

Never starts paid requests by default. The local rotation-state reservation is
committed BEFORE invoking Groq, preventing repeat paid calls after a crash.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.services.r2_news_uploader import upload_file

NEW_YORK = ZoneInfo("America/New_York")
SYMBOL_PATTERN = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z")


def enabled():
    return (os.getenv("GAEMIGTP_NEWS_STORAGE", "neon").strip().lower() == "r2"
            and os.getenv("GAEMIGTP_NEWS_AI_PAUSED", "1").strip() == "0"
            and os.getenv("GAEMIGTP_NEWS_AI_R2_ENABLED", "0").strip() == "1")


def us_exchange_day_if_due(now=None):
    """Use the existing 10:30 New York AI slot, on weekdays only.

    Worker batches run at fixed KST hours, not at exactly 10:30 ET; allow
    the next regular worker batch after the slot rather than losing that day.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_aware_time_required")
    ny = now.astimezone(NEW_YORK)
    if ny.weekday() >= 5 or (ny.hour, ny.minute) < (10, 30):
        return None
    return ny.date().isoformat()


def build_ai_payload(stock_name, symbol, exchange_day, raw, analysis, now=None):
    """Reuse the existing Groq source validation and issue display adapter."""
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("invalid_us_stock_symbol")
    if not isinstance(analysis, dict) or not isinstance(analysis.get("issues"), list):
        raise ValueError("invalid_ai_analysis")
    ops = str(Path(__file__).resolve().parents[2] / "ops")
    if ops not in sys.path:
        sys.path.insert(0, ops)
    from staged_daily_groq_issues import issue_source_metadata, MODEL
    from staged_ai_issue_display_adapter import to_issue_briefs

    now = now or dt.datetime.now(dt.timezone.utc)
    sources = issue_source_metadata(analysis["issues"], raw)
    briefs = to_issue_briefs(
        analysis["issues"], now.isoformat(), [stock_name],
        sources_by_issue=sources,
    )
    return {
        "ok": True, "source": "existing_groq_ai",
        "market": "US", "stock_name": stock_name, "symbol": symbol,
        "exchange_day": exchange_day, "generated_at": now.isoformat(),
        "model": MODEL, "count": len(briefs),
        "issue_briefs": briefs,
        # Without a verified price context, never fabricate a movement reason.
        "price_reason": None,
    }


def publish_payload(payload, *, uploader=upload_file):
    """Upload through the existing R2 transport; never overwrite news/latest."""
    symbol = str(payload.get("symbol") or "")
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("invalid_us_stock_symbol")
    path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        ) as handle:
            path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        if not uploader(path, object_key=f"news/ai/us/{symbol}.json"):
            raise RuntimeError("r2_ai_upload_failed")
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


def maybe_publish(stock_name, symbol, raw, state, persist, *, now=None,
                  analyzer=None, uploader=upload_file):
    """Reserve once per US day, durably, BEFORE the paid model invocation.

    A failed call is never automatically retried, same as the existing
    Neon-based daily call guard. AI remains disabled by default.
    """
    if not enabled():
        return "paused"
    if not SYMBOL_PATTERN.fullmatch(str(symbol or "")):
        raise ValueError("invalid_us_stock_symbol")
    day = us_exchange_day_if_due(now)
    if day is None:
        return "not_due"
    if not os.environ.get("GROQ_API_KEY", "").strip():
        return "missing_key"
    ops = str(Path(__file__).resolve().parents[2] / "ops")
    if ops not in sys.path:
        sys.path.insert(0, ops)
    from staged_daily_groq_issues import build_model_news, recent_ai_articles
    eligible, _ = build_model_news(recent_ai_articles(raw))
    if not eligible:
        return "no_eligible_articles"
    ledger = state.setdefault("_r2_ai_reservations", {})
    record = f"US:{symbol}:{day}"
    if record in ledger:
        return "already_reserved"
    # Never clear a reservation on failure. Commit it before any paid call.
    ledger[record] = "reserved"
    persist(state)
    if analyzer is None:
        from staged_daily_groq_issues import analyze_news
        analyzer = analyze_news
    try:
        analysis = analyzer(stock_name, raw)
        payload = build_ai_payload(stock_name, symbol, day, raw, analysis, now=now)
        publish_payload(payload, uploader=uploader)
    except Exception as exc:
        ledger[record] = "failed"
        persist(state)
        print(f"[news-ai-r2] stock={symbol} failed={type(exc).__name__}", flush=True)
        return "failed"
    ledger[record] = "published"
    persist(state)
    return "published"
