"""Publish a stock-specific TOP20 result to a separate Cloudflare R2 object.

Never use the shared TradingView news/latest.json key and never require Neon.
"""
from __future__ import annotations

import datetime as dt
import json
import re

from backend.services.r2_news_uploader import upload_bytes

_SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,15}\Z")


def publish_stock_news(symbol: str, stock_name: str, fingerprint: str, result: dict) -> bool:
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        raise ValueError("invalid_top20_symbol")
    if not stock_name or not isinstance(result, dict) or result.get("_news_status") != "ok":
        raise ValueError("invalid_top20_news_result")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("invalid_source_fingerprint")
    payload = {
        "schema_version": 1,
        "source": "gaemigtp-top20-news",
        "market": "US",
        "symbol": symbol,
        "stock_name": stock_name,
        "source_fingerprint": fingerprint,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "result": result,
    }
    body = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8")
    return upload_bytes(body, object_key=f"news/top20/{symbol}.json")
