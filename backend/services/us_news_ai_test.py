"""Isolated single-stock test for the live US TOP20 news analysis pipeline."""
from __future__ import annotations
import json
import re
import urllib.request
from flask import Blueprint, jsonify, request
from backend import us_news_ai_daily as job
from .ai_test import _authorized

us_news_ai_test_bp = Blueprint("us_news_ai_test", __name__)
TOP20_URL = "https://quotes.gaemigtp.com/market/trading-value?market=us"
SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,14}$")

def _top20():
    req = urllib.request.Request(TOP20_URL, headers={"Origin": "https://gaemigtp-main.pages.dev", "User-Agent": "gaemiGTP-us-news-ai-test/1.0"})
    with urllib.request.urlopen(req, timeout=12) as response:
        data = json.loads(response.read().decode("utf-8"))
    rows = data.get("items") if isinstance(data, dict) else None
    if not isinstance(rows, list): raise ValueError("top20_unavailable")
    result = []
    for index, row in enumerate(rows[:20]):
        if not isinstance(row, dict): continue
        symbol, name = str(row.get("symbol") or "").strip().upper(), str(row.get("name") or "").strip()
        if not SYMBOL.fullmatch(symbol) or not name: continue
        result.append({"rank": row.get("rank") if isinstance(row.get("rank"), int) else index + 1, "symbol": symbol, "name": name, "price": row.get("price") if type(row.get("price")) in (int, float) else None, "change_pct": row.get("change_pct") if type(row.get("change_pct")) in (int, float) else None, "industry": str(row.get("industry") or "")[:60]})
    return result

@us_news_ai_test_bp.get("/api/us-news-ai-test/config")
def config():
    if not _authorized(): return jsonify({"ok": False, "error": "unauthorized_or_disabled"}), 403
    return jsonify({"ok": True, "model": job.MODEL, "system_prompt": job.SYSTEM_PROMPT})

@us_news_ai_test_bp.get("/api/us-news-ai-test/top20")
def top20():
    if not _authorized(): return jsonify({"ok": False, "error": "unauthorized_or_disabled"}), 403
    try: return jsonify({"ok": True, "items": _top20()})
    except Exception as exc:
        print("[us-news-ai-test] top20_error=" + type(exc).__name__, flush=True)
        return jsonify({"ok": False, "error": "top20_unavailable"}), 502

@us_news_ai_test_bp.post("/api/us-news-ai-test/run")
def run_test():
    if not _authorized(): return jsonify({"ok": False, "error": "unauthorized_or_disabled"}), 403
    if (request.content_length or 0) > 10000: return jsonify({"ok": False, "error": "request_too_large"}), 413
    data = request.get_json(silent=True)
    if not isinstance(data, dict): return jsonify({"ok": False, "error": "invalid_request"}), 400
    symbol, prompt = str(data.get("symbol") or "").strip().upper(), data.get("system_prompt", job.SYSTEM_PROMPT)
    if not SYMBOL.fullmatch(symbol) or not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 6000:
        return jsonify({"ok": False, "error": "invalid_input"}), 400
    try: stock = next((row for row in _top20() if row["symbol"] == symbol), None)
    except Exception as exc:
        print("[us-news-ai-test] top20_error=" + type(exc).__name__, flush=True)
        return jsonify({"ok": False, "error": "top20_unavailable"}), 502
    if stock is None: return jsonify({"ok": False, "error": "symbol_not_in_current_top20"}), 400
    try:
        status, result, articles, tokens, diagnostics = job.analyze_stock(stock, {}, groq=lambda message: job.call_groq(message, system_prompt=prompt))
    except Exception as exc:
        print("[us-news-ai-test] " + symbol + " error=" + type(exc).__name__, flush=True)
        return jsonify({"ok": False, "error": "analysis_failed"}), 502
    payload = {"ok": True, "status": status, "model": job.MODEL, "stock": stock, "diagnostics": diagnostics or {}, "tokens": tokens, "article_count": len(articles or [])}
    if result: payload.update({"type": result["type"], "headline": result["headline"], "headline_keyword": result["headline_keyword"], "keywords": result["keywords"], "lines": result["lines"]})
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store"
    return response
