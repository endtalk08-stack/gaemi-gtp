import time
from typing import Any, Dict
from backend.services.news import get_stock_news

try:
    from backend.services.market_levels import get_market_levels
except ImportError:
    def get_market_levels(stock_name: str):
        return {}

CACHE_STORE: Dict[str, tuple[float, Dict[str, Any]]] = {}
CACHE_TTL = 300


def analyze_stock(stock_name: str) -> Dict[str, Any]:
    current_time = time.time()

    if stock_name in CACHE_STORE:
        cached_time, cached_data = CACHE_STORE[stock_name]
        if current_time - cached_time < CACHE_TTL:
            return cached_data

    try:
        news_data = get_stock_news(stock_name)
        levels_data = get_market_levels(stock_name)

        result = {
            "ok": True,
            "stock": stock_name,
            "sections": [
                {
                    "title": f"{stock_name} 종합 투자 분석",
                    "content": f"현재 {stock_name}의 시장 지표 및 최신 관련 뉴스 데이터를 기반으로 산출된 종합 리포트입니다.",
                    "levels": levels_data,
                }
            ],
            "news_items": news_data.get("news_items", []),
            "disclosures": news_data.get("disclosures", []),
            "us_filings": news_data.get("us_filings", []),
        }

        CACHE_STORE[stock_name] = (current_time, result)
        return result

    except Exception as exc:
        print(f"[Engine Error] {exc}")
        return {
            "ok": False,
            "error": "analysis_failed",
            "sections": [],
            "news_items": [],
            "disclosures": [],
            "us_filings": [],
        }
