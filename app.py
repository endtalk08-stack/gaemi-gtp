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
from backend.services.kiwoom_us_value_board import read_us_trading_value_board, read_us_live_quotes
from backend.services.us_market_close import read_brief
from backend.providers.sec_filings import fetch_panel_missing_detail

from backend.services.engine import analyze_stock, fetch_dart_disclosure_detail, fetch_dart_executive_shareholdings, fetch_us_official_filings, get_live_calendar_data, start_calendar_warmup

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.register_blueprint(ai_test_bp)
app.register_blueprint(issue_title_test_bp)
CORS(app)
install_private_access(app, FRONTEND_DIR)
start_calendar_warmup()
application = app

# One-time, read-only startup gate for verifying the DO -> Neon -> Render path.
# Does not call SEC/DART or alter news, prices, database rows, or UI responses.
if os.getenv("DISCLOSURE_NEON_READ") == "1":
    try:
        from backend.services.disclosure_transfer import read_snapshot
        for _market, _symbol in (("KR", "005930"), ("US", "AAPL")):
            _filings = read_snapshot(_market, _symbol)
            print(
                f"[disclosure-neon-readiness] market={_market} symbol={_symbol} "
                f"ready={_filings is not None} filings={len(_filings) if _filings is not None else 'unavailable'}",
                flush=True,
            )
    except Exception as _exc:
        print(
            f"[disclosure-neon-readiness] unavailable={type(_exc).__name__}",
            flush=True,
        )

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

@app.get("/disclosures/sec/detail")
def sec_right_panel_detail():
    # Only additional SEC facts for existing 30-day right-panel rows.
    index_url = str(request.args.get("url", "") or "").strip()
    try:
        detail = fetch_panel_missing_detail(index_url)
        return jsonify({"ok": True, "detail": detail})
    except ValueError:
        return jsonify({"ok": False, "error": "invalid_sec_filing"}), 400
    except Exception as exc:
        print(f"[미국 공시 상세 API] 실패: {type(exc).__name__}: {exc}")
        return jsonify({"ok": False, "error": "sec_detail_unavailable"}), 502


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
    diagnostics = []
    if market == "us":
        # Only USA trading-value Top 20 moves to the DO -> Neon Kiwoom feed.
        # The Render service never issues Kiwoom API requests.
        items = read_us_trading_value_board(limit=20, diagnostics=diagnostics)
        if items is not None:
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
            )["items"]
            for item, issue in zip(items, issue_results):
                item["issue_headline"] = issue["headline"]
    except Exception as exc:
        print(f"[market ranking issues] lookup failed: {type(exc).__name__}", flush=True)
    response = jsonify({"ok": True, "market": market, "source": "kiwoom" if market == "us" else "naver", "currency": "USD" if market == "us" else "KRW", "items": items})
    if market == "us":
        response.headers["X-Gaemi-US-Value-Provider"] = "kiwoom-neon-v1"
    return response


@app.get("/market/us-live-quotes")
def market_us_live_quotes():
    """Fast read-only latest Kiwoom quotes; never fetch a market provider or AI."""
    items = read_us_live_quotes()
    if items is None:
        response = jsonify({"ok": False, "market": "us", "items": [],
                            "error": "quotes_unavailable"})
        response.headers["Cache-Control"] = "no-store"
        return response, 503
    response = jsonify({"ok": True, "market": "us", "source": "kiwoom",
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
        result = (analyze_stock(
            stock, ticker_symbol_override=ticker,
            kr_market_override=bool(selected and selected["market"] == "kr"),
        ) if ticker else analyze_stock(stock))
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
