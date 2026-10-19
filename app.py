import os
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from backend.services.ai_test import ai_test_bp, remember_chat_analysis
from backend.services.private_access import install_private_access
from backend.services.market_rankings import (build_kr_trading_value_result, build_us_trading_value_result, build_kr_popular_result, build_us_popular_result, get_market_selection, analysis_ticker_for_selection)
from backend.services.market_issue_headlines import get_market_issue_headlines
from backend.services.us_market_close import read_brief

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

@app.get("/api/market/us-cap-headlines")
def market_us_cap_headlines():
    """Display only the registered US20 names and existing 24h AI headlines.

    Neon SELECT only. No news, quote, disclosure, rankings or AI calls.
    """
    database_url = (os.environ.get("NEWS_DATABASE_URL")
                    or os.environ.get("DATABASE_URL") or "").strip()
    if not database_url:
        return jsonify({"ok": False, "items": [], "error": "neon_not_configured"}), 503
    sql = """
        SELECT w.position, w.display_name AS name,
               COALESCE(i.headlines, ARRAY[]::text[]) AS headlines
        FROM public.fixed_watchlist_stocks AS w
        LEFT JOIN LATERAL (
            SELECT array_agg(z.headline ORDER BY z.generated_at DESC, z.id DESC) AS headlines
            FROM (
                SELECT a.id, a.headline, a.generated_at
                FROM public.news_ai_issues AS a
                WHERE a.market = 'US'
                  AND a.generated_at >= now() - interval '24 hours'
                  AND a.headline IS NOT NULL AND btrim(a.headline) <> ''
                  AND (
                      a.symbol IN (w.symbol, w.display_name)
                      OR (w.symbol = 'TSM' AND a.symbol = 'TSMC ADR')
                      OR (w.symbol = 'GOOGL'
                          AND a.symbol IN ('알파벳 Class A', '알파벳 Class C', 'GOOG'))
                      OR (w.symbol = 'AMZN' AND a.symbol = '아마존닷컴')
                      OR (w.symbol = 'MU' AND a.symbol = '마이크론 테크놀로지')
                      OR (w.symbol = 'META' AND a.symbol = '메타 플랫폼스')
                  )
                ORDER BY a.generated_at DESC, a.id DESC
                LIMIT 3
            ) AS z
        ) AS i ON TRUE
        WHERE w.market = 'US'
        ORDER BY w.position ASC
    """
    try:
        import psycopg
        with psycopg.connect(database_url, connect_timeout=3) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
    except Exception as exc:
        print("[us-cap-headlines] read_failed=" + type(exc).__name__, flush=True)
        return jsonify({"ok": False, "items": [], "error": "neon_read_unavailable"}), 503
    if len(rows) != 20 or [row[0] for row in rows] != list(range(1, 21)):
        return jsonify({"ok": False, "items": [], "error": "us20_registry_incomplete"}), 503
    return jsonify({"ok": True, "items": [
        {"name": name, "headlines": headlines or []}
        for _position, name, headlines in rows
    ]})


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
    builder = build_us_trading_value_result if market == "us" else build_kr_trading_value_result
    items = builder(limit=20)
    if items is None:
        return jsonify({"ok": False, "items": [], "error": "source_unavailable"}), 502
    issue_rows = [{"name": item.get("name"), "symbol": item.get("symbol")} for item in items]
    try:
        issue_results = get_market_issue_headlines(market, issue_rows)["items"]
        for item, issue in zip(items, issue_results):
            item["issue_headline"] = issue["headline"]
    except (ValueError, Exception) as exc:
        print(f"[market ranking issues] lookup failed: {type(exc).__name__}", flush=True)
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
    issue_rows = [{"name": item.get("name"), "symbol": item.get("symbol")} for item in items]
    try:
        issue_results = get_market_issue_headlines(market, issue_rows)["items"]
        for item, issue in zip(items, issue_results):
            item["issue_headline"] = issue["headline"]
    except (ValueError, Exception) as exc:
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
        result = get_market_issue_headlines(payload.get("market"), payload.get("items"))
    except ValueError:
        return jsonify({"ok": False, "error": "invalid_request"}), 400
    return jsonify(result)


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
