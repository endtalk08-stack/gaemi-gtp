import time
from typing import Any, Dict
from backend.services.market_levels import get_market_levels
from backend.services.news import get_stock_news

# 메모리 캐시 저장소 (종목명: (생성시간, 결과데이터))
CACHE_STORE: Dict[str, tuple[float, Dict[str, Any]]] = {}
CACHE_TTL = 300  # 캐시 유효 시간: 5분 (300초)


def analyze_stock(stock_name: str) -> Dict[str, Any]:
    current_time = time.time()

    # 1. 캐시 검증: 5분 이내 분석한 동일 종목이 있다면 즉시 반환 (0.01초 소요)
    if stock_name in CACHE_STORE:
        cached_time, cached_data = CACHE_STORE[stock_name]
        if current_time - cached_time < CACHE_TTL:
            print(f"[Cache Hit] '{stock_name}' 결과 메모리 반환")
            return cached_data

    # 2. 캐시가 없거나 만료된 경우 신규 분석 진행
    try:
        # 뉴스 및 지표 수집
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

        # 3. 신규 분석 결과를 메모리 캐시에 저장
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
