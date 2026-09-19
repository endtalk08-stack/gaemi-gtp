import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any

def get_stock_news(stock_name: str) -> Dict[str, List[Any]]:
    """
    주식 종목명을 받아 실제 네이버 뉴스 및 관련 정보를 가져오는 함수
    """
    news_items = []
    
    try:
        # 네이버 뉴스 검색 URL
        url = f"https://search.naver.com/search.naver?where=news&query={stock_name}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # 뉴스 기사 제목 및 링크 추출
            articles = soup.select(".news_tit")
            for article in articles[:5]:  # 상위 5개 기사
                news_items.append({
                    "title": article.get("title") or article.text,
                    "url": article.get("href"),
                    "source": "네이버 뉴스"
                })
    except Exception as exc:
        print(f"[News Scraping Error] {exc}")

    # 백엔드 엔진에서 필요로 하는 데이터 구조 반환
    return {
        "news_items": news_items,
        "disclosures": [],
        "us_filings": []
    }
