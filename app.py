import os
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from backend.providers.deepl_translate import translate_to_korean
from backend.services.engine import analyze_stock, get_live_calendar_data, start_calendar_warmup
from backend.services.marketaux_news import (
    CATEGORIES as MARKETAUX_CATEGORIES,
    MarketauxConfigurationError,
    MarketauxRequestError,
    fetch_marketaux_news,
    fetch_marketaux_test_feed,
)
from backend.services.news_feed import fetch_general_news, fetch_stock_news, get_news_coverage
from backend.services.news_scoring import score_stock_news, summarize_stock_flow

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)
start_calendar_warmup()
application = app

@app.get("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.get("/admin")
def admin():
    return send_from_directory(FRONTEND_DIR / "admin", "index.html")

@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "gaemiGTP"})

@app.get("/calendar")
def calendar():
    return jsonify({"ok": True, "content": get_live_calendar_data("", "")})

@app.get("/news")
def news():
    category = request.args.get("category", "전체")
    market = request.args.get("market", "전체")
    limit = request.args.get("limit", default=10, type=int)
    return jsonify({"items": fetch_general_news(category=category, region=market, limit=limit)})

@app.get("/news/stock-flow")
def stock_news_flow():
    stock = str(request.args.get("stock", "") or "").strip()
    if not stock:
        return jsonify({"ok": True, "items": [], "flow": summarize_stock_flow([])})

    # 중앙의 '왜?' 분석은 화면에 보여 줄 3개 기사보다 넓은 뉴스 흐름을 본다.
    # 패널/기존 분석 응답은 그대로 두고, 같은 공통 뉴스 가공 결과만 최대 10개까지 재사용한다.
    try:
        items = fetch_stock_news(stock, limit=10)
    except Exception as exc:
        print(f"[뉴스 흐름] 조회 실패: {type(exc).__name__}: {exc}")
        items = []

    # 수집/분류 결과를 다시 만들지 않고, 중앙 분석용으로만 설명 가능한 점수를 붙인다.
    # 화면에 대표 기사를 고르기 전에 전체 기사에서 신호/이슈/테마 흐름을 먼저 집계한다.
    scored_items = score_stock_news(items, stock)
    flow = summarize_stock_flow(scored_items)
    return jsonify({"ok": True, "items": scored_items[:10], "flow": flow})

@app.get("/news/coverage")
def news_coverage():
    return jsonify(get_news_coverage())

@app.get("/marketaux/news")
def marketaux_news():
    category = request.args.get("category", "전체")
    if category not in MARKETAUX_CATEGORIES:
        return jsonify({"ok": False, "items": [], "error": "invalid_category"}), 400
    limit = request.args.get("limit", default=3, type=int)
    try:
        items = fetch_marketaux_news(category=category, limit=limit)
    except MarketauxConfigurationError:
        return jsonify({"ok": False, "items": [], "error": "marketaux_not_configured"}), 503
    except MarketauxRequestError:
        return jsonify({"ok": False, "items": [], "error": "marketaux_unavailable"}), 502
    for item in items:
        item["original_title"] = item.get("title", "")
        item["original_description"] = item.get("description", "")
        title_ko = translate_to_korean(item["original_title"])
        description_ko = translate_to_korean(item["original_description"])
        if title_ko:
            item["title"] = title_ko
        if description_ko:
            item["description"] = description_ko
        item["translation_test"] = bool(title_ko or description_ko)
        item["provider"] = "marketaux"
        item["link"] = item.get("url", "")
        item["original_link"] = item.get("url", "")
    return jsonify({"ok": True, "category": category, "items": items})

@app.get("/marketaux/news-feed")
def marketaux_news_feed():
    try:
        feeds = fetch_marketaux_test_feed()
    except MarketauxConfigurationError:
        return jsonify({"ok": False, "feeds": {}, "error": "marketaux_not_configured"}), 503
    except MarketauxRequestError:
        return jsonify({"ok": False, "feeds": {}, "error": "marketaux_unavailable"}), 502
    return jsonify({"ok": True, "feeds": feeds})

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
        return jsonify({"sections": [], "news_items": [], "disclosures": [], "us_filings": [], "ok": False, "error": "analysis_failed"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)