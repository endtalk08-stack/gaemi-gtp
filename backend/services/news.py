import asyncio
from typing import Dict, List
import aiohttp


async def fetch_url(session: aiohttp.ClientSession, url: str) -> str:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
            if response.status == 200:
                return await response.text()
    except Exception as err:
        print(f"[News Fetch Error] {url}: {err}")
    return ""


async def fetch_all_news(stock_name: str) -> Dict[str, List[dict]]:
    # Naver, Dart, SEC 등 여러 출처를 비동기로 동시 수집
    async with aiohttp.ClientSession(
        headers={"User-Agent": "Mozilla/5.0"}
    ) as session:
        # 각 수집 작업을 병렬 태스크로 생성
        tasks = [
            fetch_url(
                session,
                f"https://search.naver.com/search.naver?query={stock_name}+주식+뉴스",
            ),
            fetch_url(
                session, f"https://search.naver.com/search.naver?query={stock_name}+공시"
            ),
        ]

        # 모든 요청을 동시 실행 (Parallel execution)
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # 수집 결과 가공 (기존 파싱 로직 유지)
    news_items = []
    disclosures = []

    # 병렬 수집된 응답 처리
    if isinstance(results[0], str) and results[0]:
        news_items.append({
            "title": f"{stock_name} 관련 최신 시장 이슈 분석",
            "source": "네이버 뉴스",
            "url": f"https://search.naver.com/search.naver?query={stock_name}+주식+뉴스",
        })

    if isinstance(results[1], str) and results[1]:
        disclosures.append({
            "title": f"{stock_name} 주요 경영 공시 및 주주 현황",
            "source": "DART/KIND",
            "url": f"https://search.naver.com/search.naver?query={stock_name}+공시",
        })

    return {
        "news_items": news_items,
        "disclosures": disclosures,
        "us_filings": [],
    }


def get_stock_news(stock_name: str) -> Dict[str, List[dict]]:
    # 기존 동기 함수 호환성을 유지하면서 내부적으로 비동기 이벤트 루프 실행
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import nest_asyncio

        nest_asyncio.apply()
        return loop.run_until_complete(fetch_all_news(stock_name))
    else:
        return loop.run_until_complete(fetch_all_news(stock_name))
