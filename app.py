import os
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from backend.services.ai_test import ai_test_bp, remember_chat_analysis
from backend.services.private_access import install_private_access
from backend.services.market_rankings import (build_kr_trading_value_result, build_us_trading_value_result, build_kr_popular_result, build_us_popular_result, get_market_selection, analysis_ticker_for_selection)
from backend.services.us_market_close_news import build_us_market_close_news_result
from backend.services.us_market_close_brief import build_us_market_close_brief

from backend.services.engine import analyze_stock, fetch_dart_disclosure_detail, fetch_dart_executive_shareholdings, fetch_us_official_filings, get_live_calendar_data, start_calendar_warmup

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.register_blueprint(ai_test_bp)
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
    return jsonify({"ok": True, "service": "gaemiGTP"})

@app.get("/calendar")
def calendar():
    return jsonify({"ok": True, "content": get_live_calendar_data("", "")})

@app.get("/disclosures/dart/detail")
def dart_disclosure_detail():
    stock_code = str(request.args.get("stock_code", "") or "").strip()
    receipt_no = str(request.args.get("receipt_no", "") or "").strip()
    report_name = str(request.args.get("report", "") or "").strip()
    if not stock_code or not receipt_no:
        return jsonify({"ok": False, "detail": {}, "error": "missing_identifier"}), 400
    try:
        detail = fetch_dart_disclosure_detail(stock_code, receipt_no, report_name)
        return jsonify({"ok": True, "detail": detail})
    except Exception as exc:
        print(f"[국내 공시 상세 API] 실패: {type(exc).__name__}: {exc}")
        return jsonify({"ok": False, "detail": {}, "error": "detail_failed"}), 200


@app.get("/debug/dart/elestock")
def debug_dart_elestock():
    stock_code = str(request.args.get("stock_code", "005930") or "").strip()
    return jsonify({
        "ok": True,
        "stock_code": stock_code,
        "items": fetch_dart_executive_shareholdings(stock_code),
    })

@app.get("/debug/sec/form4")
def debug_sec_form4():
    ticker = str(request.args.get("ticker", "NVDA") or "").upper().strip()
    filings = fetch_us_official_filings(ticker, days=30, max_results=30)
    return jsonify({
        "ok": True,
        "ticker": ticker,
        "items": [item for item in filings if str(item.get("form") or "").upper() == "4"],
    })



@app.get("/market/trading-value")
def market_trading_value():
    """Menu result; collection and interpretation stay outside the route."""
    market = str(request.args.get("market", "kr") or "").strip().lower()
    if market not in ("kr", "us"):
        return jsonify({"ok": False, "error": "invalid_market", "items": []}), 400
    builder = build_us_trading_value_result if market == "us" else build_kr_trading_value_result
    items = builder(limit=20)
    if items is None:
        return jsonify({"ok": False, "items": [], "error": "source_unavailable"}), 502
    return jsonify({"ok": True, "market": market, "source": "naver", "currency": "USD" if market == "us" else "KRW", "items": items})


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
    return jsonify({"ok": True, "market": market, "source": "naver", "ranking": "popular",
                    "currency": "USD" if market == "us" else "KRW", "items": items})


@app.get("/api/market/us-close-news")
def us_market_close_news():
    """Inspect the backend-only US close news result; no UI or stock-analysis call."""
    try:
        limit = int(request.args.get("limit", "12"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_limit"}), 400
    result = build_us_market_close_news_result(limit=limit)
    return jsonify(result), (200 if result["ok"] else 503)


@app.get("/api/market/us-close-brief")
def us_market_close_brief():
    """Central-chat market result; only server-side cached feeds are queried."""
    try:
        result = build_us_market_close_brief()
        return jsonify(result), (200 if result["ok"] else 503)
    except Exception as exc:
        print(f"[US close brief] {type(exc).__name__}: {exc}", flush=True)
        return jsonify({"ok": False, "error": "market_data_unavailable", "sections": []}), 503


@app.get("/analyze")
def analyze():
    stock = request.args.get("stock", "SK하이닉스")
    started = time.perf_counter()
    try:
        selected = get_market_selection(
            request.args.get("market"), request.args.get("menu"),
            request.args.get("symbol"), stock=stock,
        )
        ticker = analysis_ticker_for_selection(selected)
        result = analyze_stock(stock, ticker_symbol_override=ticker) if ticker else analyze_stock(stock)
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
