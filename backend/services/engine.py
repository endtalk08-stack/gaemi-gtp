import time
from typing import Any, Dict
from backend.services.news import get_stock_news

# market_levels 모듈 임포트 예외 처리 (함수명 불일치 방지)
try:
    from backend.services.market_levels import get_market_levels
except ImportError:
    def get_market_levels(stock_name: str):
        return {}

# 메모리 캐시 저장소 (종목명: (생성시간, 결과데이터))
CACHE_STORE: Dict[str, tuple[float, Dict[str, Any]]] = {}
CACHE_TTL = 300  # 5분 캐시


def analyze_stock(stock_name: str) -> Dict[str, Any]:
    current_time = time.time()

    # 1. 캐시 검증: 5분 이내 검색된 종목은 캐시 데이터 반환
    if stock_name in CACHE_STORE:
        cached_time, cached_data = CACHE_STORE[stock_name]
        if current_time - cached_time < CACHE_TTL:
            return cached_data

    # 2. 신규 분석 진행
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

        # 3. 캐시 저장
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
