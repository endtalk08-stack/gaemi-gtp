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
    "전략", "시나리오", "전망치", "forecast", "estimate", "analyst"
]

def calculate_volume_profile_levels(highs, lows, closes, volumes, bins=24):
    if not highs or not lows or not closes or not volumes:
        return {}
    min_p = min(lows)
    max_p = max(highs)
    if min_p == max_p:
        return {}
    bin_width = (max_p - min_p) / bins
    profile = [0.0] * bins
    for h, l, c, v in zip(highs, lows, closes, volumes):
        b_idx = int((c - min_p) / bin_width)
        if b_idx >= bins:
            b_idx = bins - 1
        if b_idx < 0:
            b_idx = 0
        profile[b_idx] += v
    max_idx = profile.index(max(profile))
    poc_center = min_p + (max_idx + 0.5) * bin_width
    cur_c = closes[-1]
    above_center = poc_center
    for i in range(max_idx + 1, bins):
        center_p = min_p + (i + 0.5) * bin_width
        if center_p > cur_c and profile[i] > 0:
            above_center = center_p
            break
    return {"poc": poc_center, "above": {"center": above_center}}

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
    except Exception:
        return {}

def _dart_report_score(report_name):
    text = str(report_name or "").lower()
    high = ["단일판매", "수주", "자기주식", "유상증자", "무상증자", "전환사채", "합병", "분할", "최대주주", "임상", "특허", "소송", "잠정실적", "영업이익", "배당"]
    medium = ["주요사항보고서", "타법인주식", "주식등의대량보유"]
    return sum(8 for k in high if k in text) + sum(3 for k in medium if k in text)

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
        return []
    end_date = datetime.date.today()
    begin_date = end_date - datetime.timedelta(days=days)
    try:
        params = urllib.parse.urlencode({
            "crtfc_key": OPENDART_API_KEY, "corp_code": corp_code,
            "bgn_de": begin_date.strftime("%Y%m%d"), "end_de": end_date.strftime("%Y%m%d"),
            "page_no": 1, "page_count": 30,
        })
        url = f"https://opendart.fss.or.kr/api/list.json?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if str(data.get("status", "")) not in ("000", ""):
            return []
        results = []
        for item in data.get("list", []) or []:
            report_name = str(item.get("report_nm", "")).strip()
            receipt_date = str(item.get("rcept_dt", "")).strip()
            if not report_name or not receipt_date:
                continue
            results.append({
                "date": f"{int(receipt_date[4:6])}/{int(receipt_date[6:8])}" if len(receipt_date) == 8 else receipt_date,
                "report": report_name, "score": _dart_report_score(report_name),
            })
        results.sort(key=lambda x: (x["score"], x["date"]), reverse=True)
        results = results[:3]
        DART_DISCLOSURE_CACHE[cache_key] = (now_ts, results)
        return results
    except Exception:
        return []

def fetch_yahoo_direct_v8(ticker_str):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_str}?range=6mo&interval=1d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        res = data.get('chart', {}).get('result', [])
        if not res:
            return None, None, None, None, None
        quotes = res[0].get('indicators', {}).get('quote', [{}])[0]
        closes = [float(x) for x in quotes.get('close', []) if x is not None]
        highs = [float(x) for x in quotes.get('high', []) if x is not None]
        lows = [float(x) for x in quotes.get('low', []) if x is not None]
        volumes = [float(x) for x in quotes.get('volume', []) if x is not None]
        if len(closes) < 2:
            return None, None, None, None, None
        cur_p = closes[-1]
        prev_p = closes[-2]
        ma20 = sum(closes[-20:]) / min(20, len(closes))
        volume_profile = calculate_volume_profile_levels(highs, lows, closes, volumes, bins=24)
        res_p = volume_profile.get("above", {}).get("center", 0.0) if volume_profile else 0.0
        return cur_p, prev_p, ma20, res_p, volume_profile
    except Exception:
        return None, None, None, None, None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
