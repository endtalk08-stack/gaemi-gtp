from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import datetime
import os
import re
import math
import io
import zipfile
import urllib.error
from email.utils import parsedate_to_datetime

app = Flask(__name__)
CORS(app)

# Gunicorn/WSGI compatibility: Render Start Command `gunicorn app:app` can import this object.
application = app

FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '').strip().strip('\'"')

US_KOREAN_NAMES = {
    'ORCL': '오라클 ORCL',
    'ADBE': '어도비 ADBE',
    'NVDA': '엔비디아 NVDA',
    'MSFT': '마이크로소프트 MSFT',
    'TSLA': '테슬라 TSLA',
    'AAPL': '애플 AAPL',
    'GOOGL': '구글 GOOGL',
    'AMZN': '아마존 AMZN',
    'META': '메타 META',
    'LLY': '일라이릴리 LLY',
    'NVO': '노보노디스크 NVO'
}

TICKERS = {
    '삼성전자': '005930.KS',
    'SK하이닉스': '000660.KS',
    '현대차': '005380.KS',
    '현대자동차': '005380.KS',
    '기아': '000270.KS',
    '셀트리온': '068270.KS',
    '에코프로': '086520.KQ',
    '에코프로비엠': '247540.KQ',
    '알테오젠': '196170.KQ',
    '카카오': '035720.KS',
    '카카오페이': '377300.KS',
    '카카오뱅크': '323410.KS',
    'NAVER': '035420.KS',
    '네이버': '035420.KS',
    'LG에너지솔루션': '373220.KS',
    '삼성바이오로직스': '207940.KS',
    'POSCO홀딩스': '005490.KS',
    '포스코홀딩스': '005490.KS',
    '포스코퓨처엠': '003670.KS',
    '삼성SDI': '006400.KS',
    'LG화학': '051910.KS',
    '한미반도체': '042700.KS',
    '삼천당제약': '000250.KQ',
    '레인보우로보틱스': '277810.KQ',
    '리가켐바이오': '141080.KQ',
    'HLB': '028300.KQ',
    '에이치엘비': '028300.KQ',
    '크래프톤': '259960.KS',
    '신한지주': '055550.KS',
    'KB금융': '105560.KS',
    '두산에너빌리티': '034020.KS',
    '두산로보틱스': '454910.KS',
    '현대모비스': '012330.KS',
    'HD현대중공업': '329180.KS',
    '한화에어로스페이스': '012450.KS',
    '하이브': '352820.KS',
    '한국전력': '015760.KS',
    '엔씨소프트': '036570.KS',
    '유한양행': '000100.KS',
    '루닛': '328130.KQ',
    '엔비디아': 'NVDA',
    '테슬라': 'TSLA',
    '애플': 'AAPL',
    '마이크로소프트': 'MSFT',
    '아마존': 'AMZN',
    '구글': 'GOOGL',
    '오라클': 'ORCL',
    '어도비': 'ADBE',
    '비트코인': 'BTC-USD'
}

US_CIKS = {
    "NVDA": "0001045810",
    "TSLA": "0001318605",
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "AMZN": "0001018724",
    "GOOGL": "0001652044",
    "ORCL": "0001341439",
    "ADBE": "0000796343",
    "META": "0001326801",
    "LLY": "0000059478",
    "NVO": "0000353278",
}

US_FILING_CACHE = {}

OPENDART_API_KEY = (
    os.environ.get("OPENDART_API_KEY", "").strip()
    or os.environ.get("DART_API_KEY", "").strip()
)
DART_CORP_CACHE = {"ts": 0.0, "map": {}}
DART_DISCLOSURE_CACHE = {}

US_MATERIAL_FORMS = {
    "8-K", "10-Q", "10-K", "6-K", "20-F", "424B5",
    "S-3", "S-1", "SC 13D", "SC 13G", "SC 13G/A", "4"
}

NEWS_SOURCE_PRIORITY = {
    "Reuters": 100, "로이터": 100,
    "AP": 98, "Associated Press": 98,
    "Bloomberg": 96, "블룸버그": 96,
    "Financial Times": 95, "파이낸셜타임스": 95,
    "The Wall Street Journal": 94, "월스트리트저널": 94,
    "CNBC": 92,
    "NVIDIA": 91, "엔비디아": 91,
    "연합뉴스": 90, "한국경제": 88, "매일경제": 87,
    "서울경제": 86, "전자신문": 85, "이데일리": 82,
    "머니투데이": 80, "조선비즈": 75,
}

NEWS_HARD_EVENT_WORDS = [
    "실적발표", "잠정실적", "실적", "매출", "영업이익", "순이익", "가이던스",
    "수주", "계약", "공급계약", "대형계약", "인수", "합병", "m&a",
    "투자", "증설", "감산", "증산", "출하", "판매", "가격 인상", "가격 하락",
    "공급 중단", "공급 차질", "규제", "관세", "제재", "수출 제한", "승인",
    "허가", "소송", "특허", "자사주", "배당", "유상증자", "전환사채",
    "earnings", "revenue", "profit", "guidance", "contract", "deal",
    "acquisition", "merger", "investment", "regulation", "tariff",
    "approval", "lawsuit", "buyback", "dividend", "offering",
]

NEWS_SOFT_OPINION_WORDS = [
    "전망", "예상", "분석", "목표주가", "증권가", "전문가", "기대감",
    "가능성", "주목", "관심", "수혜주", "관련주", "추천", "진단",
    "전략", "시나리오", "전망치", "forecast", "estimate", "analyst",
    "target price", "outlook"
]

# 지자체 행사, 기부, 무관한 이슈 필터링용 블랙리스트 단어
NEWS_NOISE_BLOCKLIST = [
    "고향사랑", "기부금", "교차기부", "축제", "동문회", "복지관", "시정", "구정", "군정", "임명장"
]

def fetch_dart_corp_map():
    if not OPENDART_API_KEY:
        return {}
    now = datetime.datetime.now().timestamp()
    if DART_CORP_CACHE["map"] and now - DART_CORP_CACHE["ts"] < 86400:
        return DART_CORP_CACHE["map"]
    try:
        url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={urllib.parse.quote(OPENDART_API_KEY)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = resp.read()
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            xml_name = next((name for name in zf.namelist() if name.upper().endswith("CORPCODE.XML")), None)
            if not xml_name:
                return {}
            xml_bytes = zf.read(xml_name)
        root = ET.fromstring(xml_bytes)
        mapping = {}
        for item in root.findall(".//list"):
            stock_code = (item.findtext("stock_code") or "").strip()
            corp_code = (item.findtext("corp_code") or "").strip()
            if stock_code and corp_code:
                mapping[stock_code] = corp_code
        DART_CORP_CACHE["ts"] = now
        DART_CORP_CACHE["map"] = mapping
        return mapping
    except Exception as e:
        print(f"[국내 공시] 기업코드 조회 실패: {e}")
        return {}

def _dart_report_score(report_name):
    text = str(report_name or "").lower()
    high = [
        "단일판매ㆍ공급계약", "단일판매·공급계약", "공급계약",
        "수주", "자기주식취득", "자기주식 취득", "자기주식처분",
        "유상증자", "무상증자", "전환사채", "신주인수권부사채",
        "교환사채", "합병", "분할", "영업양수", "영업양도",
        "최대주주", "주요주주", "임상", "특허", "소송",
        "잠정실적", "매출액", "영업이익", "배당",
    ]
    medium = ["주요사항보고서", "타법인주식및출자증권", "주식등의대량보유"]
    score = sum(8 for k in high if k in text)
    score += sum(3 for k in medium if k in text)
    return score

def fetch_kr_official_disclosures(stock_code, days=7):
    if not OPENDART_API_KEY or not stock_code:
        return []
    stock_code = str(stock_code).strip()
    cache_key = (stock_code, days)
    cached = DART_DISCLOSURE_CACHE.get(cache_key)
    now_ts = datetime.datetime.now().timestamp()
    if cached and now_ts - cached[0] < 300:
        return cached[1]

    corp_map = fetch_dart_corp_map()
    corp_code = corp_map.get(stock_code)
    if not corp_code:
        DART_DISCLOSURE_CACHE[cache_key] = (now_ts, [])
        return []

    end_date = datetime.date.today()
    begin_date = end_date - datetime.timedelta(days=days)
    try:
        params = urllib.parse.urlencode({
            "crtfc_key": OPENDART_API_KEY,
            "corp_code": corp_code,
            "bgn_de": begin_date.strftime("%Y%m%d"),
            "end_de": end_date.strftime("%Y%m%d"),
            "page_no": 1,
            "page_count": 30,
        })
        url = f"https://opendart.fss.or.kr/api/list.json?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if str(data.get("status", "")) not in ("000", ""):
            DART_DISCLOSURE_CACHE[cache_key] = (now_ts, [])
            return []

        results = []
        for item in data.get("list", []) or []:
            report_name = str(item.get("report_nm", "")).strip()
            receipt_date = str(item.get("rcept_dt", "")).strip()
            receipt_no = str(item.get("rcept_no", "")).strip()
            if not report_name or not receipt_date:
                continue
            results.append({
                "date": (f"{int(receipt_date[4:6])}/{int(receipt_date[6:8])}" if len(receipt_date) == 8 and receipt_date.isdigit() else receipt_date),
                "report": report_name,
                "receipt_no": receipt_no,
                "score": _dart_report_score(report_name),
            })
        results.sort(key=lambda x: (x["score"], x["date"], x["receipt_no"]), reverse=True)
        results = results[:3]
        DART_DISCLOSURE_CACHE[cache_key] = (now_ts, results)
        return results
    except Exception:
        pass
    DART_DISCLOSURE_CACHE[cache_key] = (now_ts, [])
    return []

# 개선된 뉴스 필터링 및 수집 함수 (큰따옴표 및 노이즈 원천 차단)
def fetch_clean_stock_news(keyword, count=3):
    """
    종목 코드 대신 키워드(기업명)와 이벤트 단어를 조합하여 자연어로 구글 뉴스 RSS를 검색하고,
    노이즈 단어가 포함된 기사는 걸러낸 뒤 실질적인 재료 중심의 기사를 반환합니다.
    """
    try:
        # 큰따옴표 제거 후 자연어 검색 쿼리 구성 (예: "SK하이닉스 실적 계약 수주")
        query_terms = f"{keyword} 실적 계약 수주 공시"
        encoded_query = urllib.parse.quote(query_terms)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        items = root.findall('.//item')
        
        scored_news = []
        for item in items:
            title = item.findtext('title') or ""
            link = item.findtext('link') or ""
            pub_date = item.findtext('pubDate') or ""
            
            # 1. 블랙리스트 노이즈 단어 포함 여부 확인 (지자체 기사 등 차단)
            if any(noise in title for noise in NEWS_NOISE_BLOCKLIST):
                continue
                
            # 2. 가중치 점수 산정
            score = 10
            # 하드 이벤트 단어가 포함되면 가중치 대폭 상향
            if any(ev in title.lower() for ev in NEWS_HARD_EVENT_WORDS):
                score += 50
            # 단순 전망/의견 단어는 약간 감점
            if any(op in title.lower() for op in NEWS_SOFT_OPINION_WORDS):
                score -= 10
                
            scored_news.append({
                "title": title,
                "link": link,
                "date": pub_date,
                "score": score
            })
            
        # 점수 높은 순으로 정렬 후 상위 count개 추출
        scored_news.sort(key=lambda x: x["score"], reverse=True)
        return scored_news[:count]
    except Exception as e:
        print("뉴스 수집 오류:", e)
        return []

def search_krx_code(stock_name):
    try:
        url = f"https://ac.finance.naver.com/ac?q={urllib.parse.quote(stock_name)}&q_enc=utf-8&st=1&r_lt=1&r_format=json&r_enc=utf-8"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            items = res_json.get('items', [])
            if items and len(items[0]) > 0:
                first = items[0][0]
                code = first[0]
                market = first[3].upper()
                suffix = '.KS' if 'KOSPI' in market else '.KQ'
                return f"{code}{suffix}", code
    except Exception:
        pass
    return None, None

def fetch_kr_stock_realtime(code_six):
    try:
        url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code_six}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
            'Referer': 'https://m.stock.naver.com/'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            datas = data.get('datas', [])
            if datas:
                item = datas[0]
                cur_p = float(str(item.get('closePrice', 0)).replace(',', ''))
                diff = float(str(item.get('compareToPreviousClosePrice', 0)).replace(',', ''))
                ratio = float(str(item.get('fluctuationsRatio', 0)).replace(',', ''))
                return cur_p, diff, ratio
    except Exception:
        pass
    return None, None, None

# 예시용 간단 API 라우트 구성
@app.route('/api/news', methods=['GET'])
def get_stock_news():
    keyword = request.args.get('keyword', 'SK하이닉스')
    news_list = fetch_clean_stock_news(keyword)
    return jsonify({"keyword": keyword, "news": news_list})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
