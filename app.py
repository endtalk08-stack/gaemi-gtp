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

app = Flask(__name__)
CORS(app)

# 환경 변수 로드 (공백 제거)
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '').strip()
KIWOOM_APP_KEY = os.environ.get('KIWOOM_APP_KEY', '').strip()
KIWOOM_APP_SECRET = os.environ.get('KIWOOM_APP_SECRET', '').strip()
KIWOOM_IS_MOCK = False

# 미국 대장주 한글-티커 매핑
US_KOREAN_NAMES = {
    'ORCL': '오라클(ORCL)',
    'NVDA': '엔비디아(NVDA)',
    'MSFT': '마이크로소프트(MSFT)',
    'TSLA': '테슬라(TSLA)',
    'AAPL': '애플(AAPL)',
    'GOOGL': '구글(GOOGL)',
    'AMZN': '아마존(AMZN)',
    'META': '메타(META)',
    'LLY': '일라이릴리(LLY)',
    'NVO': '노보노디스크(NVO)'
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
    'ORCL': 'ORCL',
    '비트코인': 'BTC-USD'
}

THEME_CHAIN = {
    '반도체': {'us_boss': ['NVDA', 'MSFT', 'ORCL'], 'kr_kids': ['삼성전자', 'SK하이닉스', '한미반도체']},
    '2차전지': {'us_boss': ['TSLA'], 'kr_kids': ['LG에너지솔루션', '삼성SDI', '에코프로', '에코프로비엠', '포스코퓨처엠', 'LG화학']},
    '바이오': {'us_boss': ['LLY', 'NVO'], 'kr_kids': ['삼성바이오로직스', '셀트리온', '알테오젠', '삼천당제약', '리가켐바이오', 'HLB', '유한양행']},
    '플랫폼': {'us_boss': ['GOOGL', 'META', 'AAPL'], 'kr_kids': ['NAVER', '네이버', '카카오']},
}

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

def fetch_realtime_news(stock_name):
    try:
        query = urllib.parse.quote(f"{stock_name}")
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            headlines = []
            for item in items[:3]:
                title_el = item.find('title')
                if title_el is not None and title_el.text:
                    clean = title_el.text.rsplit(' - ', 1)[0]
                    clean = re.sub(r'<[^>]+>', '', clean).strip()
                    headlines.append(clean)
            return headlines
    except Exception:
        return []

# [개선] 키움 REST API OAuth2 토큰 자동 발급 모듈
_KIWOOM_TOKEN_CACHE = None
def get_kiwoom_token():
    global _KIWOOM_TOKEN_CACHE
    if _KIWOOM_TOKEN_CACHE:
        return _KIWOOM_TOKEN_CACHE
    
    if not KIWOOM_APP_KEY or not KIWOOM_APP_SECRET:
        return None

    hosts = ['https://openapi.kiwoom.com', 'https://api.kiwoom.com']
    for host in hosts:
        try:
            url = f"{host}/oauth2/token"
            # 1. Form Data 시도
            params = urllib.parse.urlencode({
                "grant_type": "client_credentials",
                "appkey": KIWOOM_APP_KEY,
                "secretkey": KIWOOM_APP_SECRET
            }).encode('utf-8')
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Mozilla/5.0'
            }
            req = urllib.request.Request(url, data=params, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                tok = data.get('access_token') or data.get('token')
                if tok:
                    _KIWOOM_TOKEN_CACHE = tok
                    return tok
        except Exception:
            pass

        try:
            # 2. JSON Body 시도
            body = json.dumps({
                "grant_type": "client_credentials",
                "appkey": KIWOOM_APP_KEY,
                "secretkey": KIWOOM_APP_SECRET
            }).encode('utf-8')
            headers = {
                'Content-Type': 'application/json;charset=UTF-8',
                'User-Agent': 'Mozilla/5.0'
            }
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                tok = data.get('access_token') or data.get('token')
                if tok:
                    _KIWOOM_TOKEN_CACHE = tok
                    return tok
        except Exception:
            pass

    return None

def fetch_krx_supply_demand(code_six):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
            'Referer': f'https://finance.naver.com/item/main.naver?code={code_six}'
        }
        url = f"https://finance.naver.com/item/frgn.naver?code={code_six}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            html = resp.read().decode('euc-kr', 'replace')
            match = re.search(r'<tr[^>]*>\s*<td class="tc">\s*<span class="tah p10 gray03">\d{4}\.\d{2}\.\d{2}</span>.*?</tr>', html, re.DOTALL)
            if match:
                row_html = match.group(0)
                tds = row_html.split('<td')
                if len(tds) > 7:
                    inst_clean = re.sub(r'[^0-9\-]', '', tds[6])
                    foreign_clean = re.sub(r'[^0-9\-]', '', tds[7])
                    if inst_clean and foreign_clean and inst_clean != '-' and foreign_clean != '-':
                        inst_val = int(inst_clean)
                        foreign_val = int(foreign_clean)
                        if inst_val != 0 or foreign_val != 0:
                            indiv_val = -(inst_val + foreign_val)
                            return indiv_val, foreign_val, inst_val
    except Exception:
        pass
    return None, None, None

def format_shares(n):
    if n is None: return "집계 중"
    sign = "+" if n > 0 else ""
    if abs(n) >= 10000:
        return f"{sign}{n / 10000:,.1f}만 주"
    return f"{sign}{n:,}주"

def round_krw_tick(price):
    if price >= 500_000: return int(price // 1000) * 1000
    elif price >= 100_000: return int(price // 500) * 500
    elif price >= 50_000: return int(price // 100) * 100
    elif price >= 10_000: return int(price // 50) * 50
    else: return int(price // 10) * 10

def check_us_boss_earnings(boss_ticker):
    if not FINNHUB_KEY: return None
    today = datetime.date.today()
    start_date = (today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    end_date = (today + datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    try:
        url = f"https://finnhub.io/api/v1/calendar/earnings?from={start_date}&to={end_date}&symbol={boss_ticker}&token={FINNHUB_KEY}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('earningsCalendar'):
                return data['earningsCalendar'][0]
    except:
        pass
    return None

def get_official_macro_schedule():
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_tz)
    
    schedule = [
        {"name": "미국 8월 소비자물가지수(CPI) 발표", "dt": datetime.datetime(2026, 9, 11, 21, 30, tzinfo=kst_tz), "est": "0.2% (전월대비)"},
        {"name": "미국 연준 FOMC 기준금리 결정", "dt": datetime.datetime(2026, 9, 17, 3, 0, tzinfo=kst_tz), "est": "기준금리 3.50%~3.75%"},
        {"name": "미국 생산자물가지수(PPI) 발표", "dt": datetime.datetime(2026, 9, 18, 21, 30, tzinfo=kst_tz), "est": "0.2% (전월대비)"},
        {"name": "미국 개인소비지출(PCE) 물가지수", "dt": datetime.datetime(2026, 9, 25, 21, 30, tzinfo=kst_tz), "est": "2.6% (전년대비)"},
        {"name": "미국 9월 비농업 고용보고서(NFP)", "dt": datetime.datetime(2026, 10, 2, 21, 30, tzinfo=kst_tz), "est": "15만 건 (예상)"},
        {"name": "미국 9월 소비자물가지수(CPI) 발표", "dt": datetime.datetime(2026, 10, 14
