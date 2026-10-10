import os
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from backend.services.engine import analyze_stock, fetch_dart_disclosure_detail, fetch_dart_executive_shareholdings, fetch_us_official_filings, get_live_calendar_data, start_calendar_warmup

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)
start_calendar_warmup()
application = app

@app.get("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")

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


@app.get("/analyze")
def analyze():
    stock = request.args.get("stock", "SK하이닉스")
    started = time.perf_counter()
    try:
        result = analyze_stock(stock)
        response = jsonify(result)
        response.headers["X-Analysis-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.0f}"
        return response
    except Exception as exc:
        print(f"[API /analyze] unexpected error: {type(exc).__name__}: {exc}")
        return jsonify({"sections": [], "disclosures": [], "us_filings": [], "ok": False, "error": "analysis_failed"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
