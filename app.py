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
import google.generativeai as genai

from upstash_redis import Redis

app = Flask(__name__)
CORS(app)

FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '').strip().strip('\'"')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '').strip().strip('\'"')

if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
    except Exception as e:
        print("Gemini API 설정 예외:", e)

REDIS_URL = os.environ.get('UPSTASH_REDIS_REST_URL')
REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
redis_client = None

if REDIS_URL and REDIS_TOKEN:
    try:
        redis_client = Redis(url=REDIS_URL, token=REDIS_TOKEN)
        print("✅ Redis 캐시 서버 연결 성공!")
    except Exception as e:
        print("❌ Redis 연결 실패:", e)

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
    '엔비디아': 'NVDA',
    '테슬라': 'TSLA',
    '애플': 'AAPL',
    '마이크로소프트': 'MSFT',
    '아마존': 'AMZN',
    '구글': 'GOOGL',
    '비트코인': 'BTC-USD'
}

def search_krx_code(stock_name):
    # 1. 최신 네이버 증권 자동완성 API
    try:
        url = f"https://ac.stock.naver.com/ac?q={urllib.parse.quote(stock_name)}&target=stock"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://finance.naver.com'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            items = data.get('items', [])
            for it in items:
                code = it.get('code')
                type_code = it.get('typeCode', '').upper()
                if code and len(code) == 6:
                    suffix = '.KQ' if 'KOSDAQ' in type_code else '.KS'
                    return f"{code}{suffix}", code
    except Exception as e:
        print("네이버 증권 검색(ac.stock) 예외:", e)

    # 2. 구버전 네이버 금융 자동완성 보조
    try:
        url = f"https://ac.finance.naver.com/ac?q={urllib.parse.quote(stock_name)}&q_enc=utf-8&st=1&r_lt=1&r_format=json&r_enc=utf-8"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            items = res_json.get('items', [])
            if items and len(items[0]) > 0:
                first = items[0][0]
                code = first[0]
                market = first[3].upper() if len(first) > 3 else ''
                suffix = '.KQ' if 'KOSDAQ' in market else '.KS'
                return f"{code}{suffix}", code
    except Exception as e:
        print("네이버 금융 검색(ac.finance) 예외:", e)

    return None, None

def fetch_kr_stock_realtime(code_six):
    try:
        url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code_six}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
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
    except Exception as e:
        print("네이버 실시간 시세 조회 예외:", e)
    return None, None, None

def fetch_krx_trend_and_supply(code_six):
    try:
        url = f"https://m.stock.naver.com/api/stock/{code_six}/trend?page=1&pageSize=20"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Referer': 'https://m.stock.naver.com/'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and isinstance(data, list):
                prices = []
                for row in data:
                    cp = row.get('closePrice')
                    if cp:
                        prices.append(float(str(cp).replace(',', '')))
                ma20 = sum(prices) / len(prices) if prices else 0
                resistance = max(prices) if prices else 0

                sum_foreign = 0
                sum_inst = 0
                sum_indiv = 0
                valid_days = 0

                for row in data[:5]:
                    frgn = row.get('foreignerPureBuyQuant') or 0
                    insti = row.get('organPureBuyQuant') or row.get('institutionPureBuyQuant') or 0
                    indiv = row.get('individualPureBuyQuant') or 0

                    sum_foreign += int(str(frgn).replace(',', ''))
                    sum_inst += int(str(insti).replace(',', ''))
                    sum_indiv += int(str(indiv).replace(',', ''))
                    valid_days += 1

                return ma20, resistance, sum_foreign, sum_inst, sum_indiv, valid_days
    except Exception as e:
        print("네이버 수급 집계 예외:", e)
    return 0, 0, None, None, None, 0

def fetch_yahoo_direct_v8(ticker_str):
    try:
        stock = yf.Ticker(ticker_str)
        hist = stock.history(period="1mo")
        if not hist.empty and len(hist) >= 2:
            cur_p = float(hist['Close'].iloc[-1])
            prev_p = float(hist['Close'].iloc[-2])
            
            closes = hist['Close'].dropna().tolist()
            ma20 = sum(closes) / len(closes) if closes else cur_p
            
            highs = hist['High'].dropna().tolist()
            res_p = max(highs) if highs else cur_p * 1.05
            
            return cur_p, prev_p, ma20, res_p
    except Exception as e:
        print("야후 데이터 조회 예외:", e)
    return None, None, None, None

def filter_core_news_with_gemini(headlines, stock_name):
    if not headlines or not GEMINI_KEY:
        return headlines[:3]
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"주식 전문가 관점에서 {stock_name} 관련 뉴스 중 주가 영향력이 가장 큰 핵심 뉴스 최대 3개를 골라줘.\n"
            f"중복되거나 유사한 내용의 기사는 하나만 남겨야 해.\n"
            f"단순 광고/찌라시는 제외하고, 설명이나 번호 없이 뉴스 헤드라인 내용만 한 줄에 하나씩 출력해.\n\n"
            + "\n".join(headlines)
        )
        response = model.generate_content(prompt)
        filtered = [line.strip().lstrip('1234567890.-•* ') for line in response.text.strip().split('\n') if line.strip()]
        return filtered[:3] if filtered else headlines[:3]
    except Exception as e:
        print("Gemini 필터링 건너뛰기:", e)
        return headlines[:3]

def fetch_realtime_news(stock_name):
    cache_key = f"news_v3_{stock_name}"
    
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                if isinstance(cached_data, str):
                    cached_data = json.loads(cached_data)
                return cached_data
        except Exception as e:
            print("Redis 읽기 에러:", e)

    try:
        query = urllib.parse.quote(f"{stock_name}")
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            headlines = []
            for item in items:
                title_el = item.find('title')
                if title_el is not None and title_el.text:
                    title = title_el.text
                    title = re.sub(r'\[.*?\]', '', title)
                    title = re.sub(r'<[^>]+>', '', title)
                    title = re.sub(r'\s*[-–—―|]\s*[^-–—―|]+$', '', title)
                    title = re.sub(r'[\.…]+\s*$', '', title)
                    title = re.sub(r'\.{2,}|…', ' · ', title)
                    clean = title.strip().strip('"\'“”')
                    if clean and clean not in headlines:
                        headlines.append(clean)
                    if len(headlines) >= 12:
                        break
            
            filtered_news = filter_core_news_with_gemini(headlines, stock_name)
            
            if redis_client and filtered_news:
                try:
                    redis_client.setex(cache_key, 86400, json.dumps(filtered_news, ensure_ascii=False))
                except Exception as e:
                    print("Redis 쓰기 에러:", e)
                    
            return filtered_news
    except Exception as e:
        print("구글 뉴스 검색 예외:", e)
        return []

def format_shares(n):
    if n is None: return "0주"
    sign = "+" if n > 0 else ""
    if abs(n) >= 10000:
        return f"{sign}{n / 10000:,.1f}만주"
    return f"{sign}{n:,}주"

def round_krw_tick(price):
    if price is None: return 0
    try:
        p = float(price)
        if math.isnan(p) or math.isinf(p) or p <= 0: return 0
        if p >= 500_000: return int(p // 1000) * 1000
        elif p >= 100_000: return int(p // 500) * 500
        elif p >= 50_000: return int(p // 100) * 100
        elif p >= 10_000: return int(p // 50) * 50
        else: return int(p // 10) * 10
    except Exception:
        return 0

def get_live_calendar_data(stock_name, ticker_symbol):
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_tz)
    weekdays = ['월', '화', '수', '목', '금', '토', '일']

    master_events = [
        {"name": "미국 8월 생산자물가지수 #PPI", "dt": datetime.datetime(2026, 9, 10, 21, 30, tzinfo=kst_tz), "est": "0.2%", "type": "ppi"},
        {"name": "#오라클 ORCL 실적 발표", "dt": datetime.datetime(2026, 9, 11, 5, 0, tzinfo=kst_tz), "est": "예상 EPS $1.33", "type": "earnings", "target": "글로벌 AI·클라우드 대장주"},
        {"name": "#어도비 ADBE 실적 발표", "dt": datetime.datetime(2026, 9, 11, 5, 0, tzinfo=kst_tz), "est": "예상 EPS $6.08", "type": "earnings", "target": "글로벌 AI·소프트웨어 대장주"},
        {"name": "미국 8월 소비자물가지수 #CPI", "dt": datetime.datetime(2026, 9, 11, 21, 30, tzinfo=kst_tz), "est": "0.2%", "type": "cpi"},
        {"name": "미국 연준 #FOMC 기준금리 결정", "dt": datetime.datetime(2026, 9, 17, 3, 0, tzinfo=kst_tz), "est": "기준금리 3.50%~3.75%", "type": "fomc"},
        {"name": "미국 개인소비지출 #PCE 물가지수", "dt": datetime.datetime(2026, 9, 25, 21, 30, tzinfo=kst_tz), "est": "2.6%", "type": "pce"}
    ]

    master_events.sort(key=lambda x: x['dt'])
    upcoming = [ev for ev in master_events if ev['dt'] >= now_kst]
    if not upcoming:
        upcoming = master_events[:4]

    check_lines = []
    for ev in upcoming[:4]:
        e_dt = ev['dt']
        e_wd = weekdays[e_dt.weekday()]
        e_time = e_dt.strftime(f"%m/%d({e_wd}) %H:%M")
        check_lines.append(f"• {e_time} {ev['name']}")

    return "🗓️ 이번 주 핵심 개미 캘린더 ★★★\n" + "\n".join(check_lines)

@app.route('/')
def home():
    return "gaemiGTP 대화형 수급 & 리포트 엔진 가동 중!"

@app.route('/analyze', methods=['GET'])
def analyze():
    raw_name = request.args.get('stock', '삼성전자').strip()
    ticker_symbol = TICKERS.get(raw_name)
    clean_code = None

    try:
        if ticker_symbol:
            clean_code = ''.join(filter(str.isdigit, ticker_symbol))
        elif re.match(r'^\d{6}$', raw_name):
            clean_code = raw_name
            ticker_symbol = f"{clean_code}.KS"
        elif re.match(r'^[A-Za-z\-]+$', raw_name):
            ticker_symbol = raw_name.upper()
        else:
            ticker_symbol, clean_code = search_krx_code(raw_name)

        # 종목을 찾지 못했을 때 억지로 타 종목 데이터를 불러오지 않고 에러 반환
        if not ticker_symbol:
            return jsonify({
                "sections": [
                    {
                        "title": f"⚠️ '{raw_name}' 종목을 찾을 수 없습니다",
                        "content": f"'{raw_name}' 종목코드를 확인할 수 없어.\n정확한 종목명이나 6자리 종목코드(예: 000500)를 입력해줘!"
                    }
                ]
            })

        is_krw = ('-' not in ticker_symbol and ticker_symbol.endswith(('.KS', '.KQ'))) or (clean_code and len(clean_code) == 6)

        current_price = 0.0
        change_pct = 0.0
        ma20 = 0.0
        resistance_price = 0.0
        supply_content = ""

        if is_krw and clean_code:
            cur_p, diff, ratio = fetch_kr_stock_realtime(clean_code)
            ma20_val, res_val, f_5d, i_5d, ind_5d, v_days = fetch_krx_trend_and_supply(clean_code)

            # 네이버 실시간 조회가 일시 실패할 경우 yfinance로 2차 보완
            if not cur_p:
                yp, yprev, yma, yres = fetch_yahoo_direct_v8(ticker_symbol)
                if yp:
                    cur_p = yp
                    ratio = ((yp - yprev) / yprev) * 100 if yprev else 0.0
                    ma20_val = yma
                    res_val = yres

            current_price = cur_p or 0.0
            change_pct = ratio if ratio is not None else 0.0
            ma20 = ma20_val if ma20_val else current_price * 0.95
            resistance_price = res_val if res_val else current_price * 1.05

            clean_price = round_krw_tick(current_price)
            clean_ma20 = round_krw_tick(ma20)
            clean_res = round_krw_tick(resistance_price)
            price_str = f"{clean_price:,}원"
            ma20_str = f"{clean_ma20:,}원"
            res_str = f"{clean_res:,}원"

            if f_5d is not None and i_5d is not None and v_days > 0:
                f_abs = format_shares(f_5d)
                i_abs = format_shares(i_5d)
                ind_abs = format_shares(ind_5d)
                tag_line = f"#외국인 {f_abs} #기관 {i_abs} #개인 {ind_abs}"

                if f_5d > 0 and i_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 외인과 기관이 쌍끌이 순매수 중이야.\n메이저 세력이 바닥을 다지는 흐름인지 체크해 봐."
                elif f_5d < 0 and i_5d < 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 큰손들이 물량을 덜어내는 구간이야.\n개인만 매수세를 받는 자리일 수 있으니 주의 깊게 관찰해."
                elif f_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일간 외국인이 순매수로 물량을 모아가는 추세야."
                elif i_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 국내 기관 중심의 순매수가 유입되고 있어."
                else:
                    supply_content = f"{tag_line}\n\n최근 5일간 뚜렷한 세력 매수 없이 팽팽한 흐름이야."
            else:
                supply_content = "현재 수급 데이터를 집계 중이야. 지지선과 이동평균선을 우선 참고해줘."

        else:
            cur_p, prev_p, ma20_val, res_val = fetch_yahoo_direct_v8(ticker_symbol)
            if cur_p and prev_p:
                current_price = cur_p
                change_pct = ((cur_p - prev_p) / prev_p) * 100
                ma20 = ma20_val
                resistance_price = res_val
            else:
                current_price = 0.0
                change_pct = 0.0

            price_str = f"${current_price:,.2f}"
            ma20_str = f"${ma20:,.2f}"
            res_str = f"${resistance_price:,.2f}"
            supply_content = "미국 주식은 옵션 및 수급 지표를 확인하며 20일 이동평균선 지지 여부를 체크해."

        if change_pct >= 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = f"{raw_name} {change_pct:+.2f}% 강한 상승세 기록 중!"
        elif 0.5 <= change_pct < 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = f"{raw_name} {change_pct:+.2f}% 우상향 흐름 유지 중이야."
        elif -0.5 < change_pct < 0.5:
            status_emoji, title_word = '⚖️', '보합일까'
            intro_ment = f"{raw_name} {change_pct:+.2f}% 보합권에서 방향성 탐색 중이야."
        elif -5.0 < change_pct <= -0.5:
            status_emoji, title_word = '❄️', '숨고르기일까'
            intro_ment = f"{raw_name} {change_pct:+.2f}% 조정 흐름을 보이고 있어."
        else:
            status_emoji, title_word = '❄️', '빠질까'
            intro_ment = f"{raw_name} {change_pct:+.2f}% 하락세가 지속 중이니 지지선 체크가 필요해."

        news_list = fetch_realtime_news(raw_name)
        news_lines = "\n".join([f"📰 \"{title}\"" for title in news_list]) if news_list else f"📰 \"{raw_name} 관련 최신 속보 집계 중\""

        sections = [
            {
                "title": f"{status_emoji} 그래서 오늘은 왜 {title_word}?",
                "content": f"{intro_ment}\n\n현재 주가는 {price_str} 기록 중!\n\n{news_lines}",
                "tags": [f"#{raw_name}", f"#{change_pct:+.2f}%"]
            },
            {
                "title": "큰손들은 담고 있을까, 털고 있을까?",
                "content": supply_content
            },
            {
                "title": "여기 깨지면 주의해",
                "content": f"#생존 지지선 {ma20_str}\n해당 지지선 이탈 시 매물 압박이 커질 수 있으니 리스크 관리가 필요해.\n\n#단기 저항선 {res_str}\n단기 전고점 부근으로 저항 매물이 출회될 수 있는 구간이야."
            },
            {
                "title": "오늘 밤, 이번 주 일정",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ]
        return jsonify({"sections": sections})

    except Exception as e:
        print("서버 처리 예외:", e)
        return jsonify({
            "sections": [
                {
                    "title": "⚠️ 데이터 조회 중 오류가 발생했습니다",
                    "content": f"'{raw_name}' 종목 정보를 불러오는 데 일시적인 통신 오류가 발생했어. 잠시 후 다시 검색해줘!"
                }
            ]
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
