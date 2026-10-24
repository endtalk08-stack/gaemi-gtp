import os
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from backend.services.ai_test import ai_test_bp, remember_chat_analysis
from backend.services.issue_title_test import issue_title_test_bp
from backend.services.private_access import install_private_access
from backend.services.market_rankings import (build_kr_trading_value_result, build_us_trading_value_result, build_kr_popular_result, build_us_popular_result, get_market_selection, analysis_ticker_for_selection)
from backend.services.market_issue_headlines import get_market_issue_headlines
from backend.services.news_result import get_shared_stock_news_result
from backend.services.news_freshness import issue_mode_for_question, normalize_issue_mode
from backend.services.kiwoom_us_value_board import read_us_trading_value_board
from backend.services.us_price_push import accept_signed_quotes, read_memory_quotes
from backend.services.us_market_close import read_brief
from backend.services.voice_tts import voice_tts_bp

from backend.services.engine import analyze_stock, get_live_calendar_data, start_calendar_warmup

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.register_blueprint(ai_test_bp)
app.register_blueprint(issue_title_test_bp)
app.register_blueprint(voice_tts_bp)
CORS(app)
install_private_access(app, FRONTEND_DIR)
start_calendar_warmup()
application = app


@app.get("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.get("/ai-test")
def ai_test_page():
    return send_from_directory(FRONTEND_DIR, "ai-test.html")

@app.get("/health")
def health():
    """Read-only process health: counts only; never reveal live prices or identities."""
    quotes = read_memory_quotes() or []
    fresh = sum(1 for quote in quotes if not quote["stale"])
    return jsonify({"ok": True, "service": "gaemiGTP",
                    "us_live_feed": {"fresh_symbols": fresh,
                                     "cached_symbols": len(quotes),
                                     "receiving": bool(fresh)}})

@app.get("/calendar")
def calendar():
    return jsonify({"ok": True, "content": get_live_calendar_data("", "")})


@app.get("/api/market/us-close")
def market_us_close():
    """Only read a completed 24h US close brief; never collect or invoke AI."""
    try:
        brief = read_brief()
    except Exception as exc:
        print("[us market close] db read failed: " + type(exc).__name__, flush=True)
        return jsonify({"ok": False, "error": "market_close_unavailable"}), 503
    return jsonify({"ok": True, "available": bool(brief), **(brief or {})})


@app.get("/market/trading-value")
def market_trading_value():
    """Menu result; collection and interpretation stay outside the route."""
    market = str(request.args.get("market", "kr") or "").strip().lower()
    if market not in ("kr", "us"):
        return jsonify({"ok": False, "error": "invalid_market", "items": []}), 400
    diagnostics = []
    if market == "us":
        # Only USA trading-value Top 20 moves to the DO -> Neon Kiwoom feed.
        # The Render service never issues Kiwoom API requests.
        items = read_us_trading_value_board(limit=20, diagnostics=diagnostics)
        if items is not None:
            # DO real-time ticks override the minute-level ranking source in memory.
            latest = {q["symbol"]: q for q in (read_memory_quotes() or []) if not q["stale"]}
            for item in items:
                quote = latest.get(item["symbol"])
                if quote:
                    item["price"] = quote["price"]
                    if quote["change_pct"] is not None:
                        item["change_pct"] = quote["change_pct"]
            from backend.services.market_rankings import _remember_market_result
            _remember_market_result("us", "value", items)
    else:
        items = build_kr_trading_value_result(limit=20)
    if items is None:
        response = jsonify({"ok": False, "items": [], "error": "source_unavailable",
                            "provider_status": diagnostics[-1] if diagnostics else "unavailable"})
        if market == "us":
            response.headers["X-Gaemi-US-Value-Provider"] = "kiwoom-neon-v1"
        return response, 502
    issue_rows = [{"name": item.get("name"), "symbol": item.get("symbol")} for item in items]
    try:
        # The ranking list is already source-normalized, but one bad identity
        # must not discard the valid stocks' existing Neon issue headlines.
        if issue_rows:
            issue_results = get_market_issue_headlines(
                market, issue_rows, skip_invalid=True,
                issue_mode=normalize_issue_mode(request.args.get("issue_mode")),
            )["items"]
            for item, issue in zip(items, issue_results):
                item["issue_headline"] = issue["headline"]
    except Exception as exc:
        print(f"[market ranking issues] lookup failed: {type(exc).__name__}", flush=True)
    response = jsonify({"ok": True, "market": market, "source": "kiwoom" if market == "us" else "naver", "currency": "USD" if market == "us" else "KRW", "items": items})
    if market == "us":
        response.headers["X-Gaemi-US-Value-Provider"] = "kiwoom-neon-v1"
    return response


@app.post("/internal/market/us-price-push")
def market_us_price_push():
    """Signed, direct DO -> Render price relay. No database writes or external calls."""
    if (request.content_length or 0) > 6000:
        return jsonify({"ok": False, "error": "too_large"}), 413
    raw = request.get_data(cache=False, as_text=False)
    ok, reason = accept_signed_quotes(
        raw, request.headers.get("X-Gaemi-Timestamp", ""),
        request.headers.get("X-Gaemi-Signature", ""),
    )
    if not ok:
        return jsonify({"ok": False, "error": reason}), 403
    return "", 204


@app.get("/market/us-live-quotes")
def market_us_live_quotes():
    """In-memory quote feed only: never query Neon, Redis, Kiwoom or filesystem."""
    items = read_memory_quotes()
    if items is None:
        response = jsonify({"ok": False, "market": "us", "items": [],
                            "error": "waiting_for_direct_feed"})
        response.headers["Cache-Control"] = "no-store"
        return response, 503
    response = jsonify({"ok": True, "market": "us", "source": "kiwoom-direct",
                        "items": items})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/market/popular")
def market_popular():
    """Separate popular ranking menu result; never reinterpret traded volume."""
    market = str(request.args.get("market", "kr") or "").strip().lower()
    if market not in ("kr", "us"):
        return jsonify({"ok": False, "error": "invalid_market", "items": []}), 400
    builder = build_us_popular_result if market == "us" else build_kr_popular_result
    items = builder(limit=20)
    if items is None:
        return jsonify({"ok": False, "items": [], "error": "source_unavailable"}), 502
    issue_rows = [{"name": item.get("name"), "symbol": item.get("symbol")} for item in items]
    try:
        # The ranking list is already source-normalized, but one bad identity
        # must not discard the valid stocks' existing Neon issue headlines.
        if issue_rows:
            issue_results = get_market_issue_headlines(
                market, issue_rows, skip_invalid=True,
                issue_mode=normalize_issue_mode(request.args.get("issue_mode")),
            )["items"]
            for item, issue in zip(items, issue_results):
                item["issue_headline"] = issue["headline"]
    except Exception as exc:
        print(f"[market ranking issues] lookup failed: {type(exc).__name__}", flush=True)
    return jsonify({"ok": True, "market": market, "source": "naver", "ranking": "popular",
                    "currency": "USD" if market == "us" else "KRW", "items": items})


@app.post("/market/issue-headlines")
def market_issue_headlines():
    """Reuse verified stock-news results, one representative issue per ranking row."""
    if (request.content_length or 0) > 4500:
        return jsonify({"ok": False, "error": "request_too_large"}), 413
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "invalid_request"}), 400
    try:
        result = get_market_issue_headlines(
            payload.get("market"), payload.get("items"),
            issue_mode=normalize_issue_mode(payload.get("issue_mode")),
        )
    except ValueError:
        return jsonify({"ok": False, "error": "invalid_request"}), 400
    return jsonify(result)


@app.get("/api/news/issues")
def stock_news_issues():
    """Fast read-only issue endpoint. No AI calls, news collection or DB writes."""
    stock = str(request.args.get("stock") or "").strip()
    market = str(request.args.get("market") or "us").lower()
    if not stock or len(stock) > 60 or market not in ("us", "kr"):
        return jsonify({"ok": False, "error": "invalid_input", "issue_briefs": []}), 400
    symbol = str(request.args.get("symbol") or "").strip().upper()
    if symbol and (len(symbol) > 32 or not all(c.isascii() and (c.isalnum() or c in ".^-_") for c in symbol)):
        return jsonify({"ok": False, "error": "invalid_symbol", "issue_briefs": []}), 400
    mode = issue_mode_for_question(
        request.args.get("question"),
        explicit=request.args.get("issue_mode", "code"),
    )
    result = get_shared_stock_news_result(
        stock, market="미국" if market == "us" else "국내",
        symbol=symbol or None, issue_mode=mode,
    )
    return jsonify({
        "ok": True, "stock": stock, "market": market,
        "issue_mode": mode,
        "issue_display_channel": result.get("_issue_display_channel", "unavailable"),
        "issue_briefs": result.get("issue_briefs", []),
        "issue_channels": result.get("issue_channels", {}),
    })


@app.get("/analyze")
def analyze():
    stock = request.args.get("stock", "SK하이닉스")
    issue_mode = issue_mode_for_question(
        request.args.get("question"),
        explicit=request.args.get("issue_mode"),
    )
    started = time.perf_counter()
    try:
        selected = get_market_selection(
            request.args.get("market"), request.args.get("menu"),
            request.args.get("symbol"), stock=stock,
        )
        ticker = analysis_ticker_for_selection(selected)
        result = (analyze_stock(
            stock, ticker_symbol_override=ticker,
            kr_market_override=bool(selected and selected["market"] == "kr"),
            issue_mode=issue_mode,
        ) if ticker else analyze_stock(stock, issue_mode=issue_mode))
        remember_chat_analysis(stock, result, selection=selected)
        response = jsonify(result)
        response.headers["X-Analysis-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.0f}"
        return response
    except Exception as exc:
        print(f"[API /analyze] unexpected error: {type(exc).__name__}: {exc}")
        return jsonify({"sections": [], "disclosures": [], "us_filings": [], "ok": False, "error": "analysis_failed"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
