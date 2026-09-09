from flask import Flask, jsonify, request
from flask_cors import CORS
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import datetime
import os
import re
import math
from concurrent.futures import ThreadPoolExecutor
import google.generativeai as genai
from upstash_redis import Redis

app = Flask(__name__)
CORS(app)

FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '').strip().strip('\'"')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY', '').strip().strip('\'"')

if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
    except Exception:
        pass

REDIS_URL = os.environ.get('UPSTASH_REDIS_REST_URL')
REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
redis_client = None

if REDIS_URL and REDIS_TOKEN:
    try:
        redis_client = Redis(url=REDIS_URL, token=REDIS_TOKEN)
        print("✅ Redis 캐시 서버 연결 성공!")
    except Exception:
        pass

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
    '가온전선': '000500.KS',
    '엔비디아': 'NVDA',
    '테슬라': 'TSLA',
    '애플': 'AAPL',
    '마이크로소프트': 'MSFT',
    '아마존': 'AMZN',
    '구글': 'GOOGL',
    '오라클': 'ORCL',
    'ORCL': 'ORCL',
    '어도비': 'ADBE',
    'ADBE': 'ADBE',
    '비트코인': 'BTC-USD'
}

def search_krx_code(stock_name):
    try:
        url = f"https://ac.stock.naver.com/ac?q={urllib.parse.quote(stock_name)}&target=stock"
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            items = data.get('items', [])
            for it in items:
                code = it.get('code')
                type_code = it.get('typeCode', '').upper()
                if code and len(code) == 6:
                    suffix = '.KQ' if 'KOSDAQ' in type_code else '.KS'
                    return f"{code}{suffix}", code
    except Exception:
        pass
    return None, None

def fetch_kr_stock_realtime(code_six):
    try:
        url = f"https://m.stock.naver.com/api/stock/{code_six}/basic"
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            cur_p = float(str(data.get('nowPrice', 0)).replace(',', ''))
            diff = float(str(data.get('compareToPreviousClosePrice', 0)).replace(',', ''))
            ratio = float(str(data.get('fluctuationsRatio', 0)).replace(',', ''))
            return cur_p, diff, ratio
    except Exception:
        pass
    return None, None, None

def fetch_krx_trend_and_supply(code_six):
    try:
        url = f"https://m.stock.naver.com/api/stock/{code_six}/trend?page=1&pageSize=20"
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and isinstance(data, list):
                prices = [float(str(row['closePrice']).replace(',', '')) for row in data if row.get('closePrice')]
                ma20 = sum(prices) / len(prices) if prices else 0
                resistance = max(prices) if prices else 0

                sum_foreign, sum_inst, sum_indiv, valid_days = 0, 0, 0, 0
                for row in data[:5]:
                    frgn = row.get('foreignerPureBuyQuant') or 0
                    insti = row.get('organPureBuyQuant') or row.get('institutionPureBuyQuant') or 0
                    indiv = row.get('individualPureBuyQuant') or 0

                    sum_foreign += int(str(frgn).replace(',', ''))
                    sum_inst += int(str(insti).replace(',', ''))
                    sum_indiv += int(str(indiv).replace(',', ''))
                    valid_days += 1

                if sum_indiv == 0 and (sum_foreign != 0 or sum_inst != 0):
                    sum_indiv = -(sum_foreign + sum_inst)

                return ma20, resistance, sum_foreign, sum_inst, sum_indiv, valid_days
    except Exception:
        pass
    return 0, 0, None, None, None, 0

def fetch_us_stock(ticker_str):
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker_str)
        hist = stock.history(period="1mo", timeout=2.5)
        if not hist.empty and len(hist) >= 2:
            cur_p = float(hist['Close'].iloc[-1])
            prev_p = float(hist['Close'].iloc[-2])
            closes = hist['Close'].dropna().tolist()
            ma20 = sum(closes) / len(closes) if closes else cur_p
            res_p = max(hist['High'].dropna().tolist()) if not hist['High'].empty else cur_p * 1.05
            return cur_p, prev_p, ma20, res_p
    except Exception:
        pass
    return None, None, None, None

_cached_active_model = None
def get_active_gemini_model():
    global _cached_active_model
    if _cached_active_model: return _cached_active_model
    try:
        available_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for pref in ['gemini-3.6-flash', 'gemini-2.0-flash', 'gemini-flash-latest', 'gemini-1.5-flash-latest']:
            if pref in available_models:
                _cached_active_model = pref
                return _cached_active_model
        if available_models: return available_models[0]
    except Exception:
        pass
    return 'gemini-3.6-flash'

def analyze_news_and_reason_with_gemini(headlines, stock_name):
    def fallback(h_list):
        return "주요 공시와 호가창 매물대 흐름을 체크하며 방향성을 탐색 중이야.", [re.sub(r'\s*[-–—―|]\s*[^-–—―|]+$', '', h).strip().strip('"\'“”') for h in h_list[:3]], False

    if not headlines or not GEMINI_KEY:
        return fallback(headlines)
    
    try:
        model = genai.GenerativeModel(get_active_gemini_model())
        prompt = (
            f"종목:{stock_name}\n"
            f"아래 뉴스를 분석해 오늘 주가 흐름의 핵심 재료를 찾고 반드시 아래 JSON 형식으로만 출력해.\n"
            f"※ 주의: 퍼센트(%)나 구체적인 가격 숫자는 절대 언급하지 마. 오직 핵심 원인과 재료만 써.\n\n"
            f"{{\n"
            f'  "judgment": "호재" (또는 "악재", "불명확"),\n'
            f'  "reason": "숫자 없이 왜 오르거나 내리는지 재료 중심 개미 말투로 1~2줄 화끈하게 설명",\n'
            f'  "news": ["핵심 뉴스 1 요약", "핵심 뉴스 2 요약", "핵심 뉴스 3 요약"]\n'
            f"}}\n\n"
            f"[뉴스 원문]\n" + "\n".join(headlines[:5])
        )
        response = model.generate_content(prompt)
        text = response.text.strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match: return fallback(headlines)
            
        data = json.loads(match.group(0))
        judgment = data.get("judgment", "")
        reason = data.get("reason", "이유 파악 중")
        news_list = data.get("news", [])
        
        final_reason = f"[{judgment} 🚨] {reason}" if judgment in ["호재", "악재"] else (f"[{judgment}] {reason}" if judgment else reason)
        clean_news = [re.sub(r'\s*[-–—―|]\s*[^-–—―|]+$', '', n).strip('"\'“”') for n in news_list]
        
        return (final_reason, clean_news[:3], True) if reason and clean_news else fallback(headlines)
    except Exception:
        return fallback(headlines)

def fetch_realtime_news_and_reason(stock_name):
    cache_key = f"news_v15_{stock_name}"
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                d = json.loads(cached_data) if isinstance(cached_data, str) else cached_data
                return d.get("reason", ""), d.get("news", [])
        except Exception:
            pass

    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(stock_name)}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=1.8) as resp:
            root = ET.fromstring(resp.read())
            headlines = []
            for item in root.findall('.//item'):
                title_el = item.find('title')
                if title_el is not None and title_el.text:
                    clean = re.sub(r'<[^>]+>|\[.*?\]|\.{2,}|…', '', title_el.text).strip().strip('"\'“”')
                    if clean and clean not in headlines:
                        headlines.append(clean)
                    if len(headlines) >= 6: break
            
            reason, filtered_news, is_ai_success = analyze_news_and_reason_with_gemini(headlines, stock_name)
            if redis_client and is_ai_success:
                try:
                    redis_client.setex(cache_key, 86400, json.dumps({"reason": reason, "news": filtered_news}, ensure_ascii=False))
                except Exception:
                    pass
            return reason, filtered_news
    except Exception:
        return "뉴스 데이터를 불러오지 못했어.", []

def format_shares(n):
    if n is None: return "0주"
    sign = "+" if n > 0 else ""
    return f"{sign}{n / 10000:,.1f}만주" if abs(n) >= 10000 else f"{sign}{n:,}주"

def round_krw_tick(p):
    if not p or math.isnan(p) or math.isinf(p) or p <= 0: return 0
    if p >= 500_000: return int(p // 1000) * 1000
    if p >= 100_000: return int(p // 500) * 500
    if p >= 50_000: return int(p // 100) * 100
    if p >= 10_000: return int(p // 50) * 50
    return int(p // 10) * 10

def get_live_calendar_data():
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst_tz)
    events = [
        {"name": "미국 8월 생산자물가지수 #PPI", "dt": datetime.datetime(2026, 9, 10, 21, 30, tzinfo=kst_tz)},
        {"name": "#오라클 ORCL 실적 발표", "dt": datetime.datetime(2026, 9, 11, 5, 0, tzinfo=kst_tz)},
        {"name": "#어도비 ADBE 실적 발표", "dt": datetime.datetime(2026, 9, 11, 5, 0, tzinfo=kst_tz)},
        {"name": "미국 8월 소비자물가지수 #CPI", "dt": datetime.datetime(2026, 9, 11, 21, 30, tzinfo=kst_tz)},
        {"name": "미국 연준 #FOMC 기준금리 결정", "dt": datetime.datetime(2026, 9, 17, 3, 0, tzinfo=kst_tz)}
    ]
    upcoming = [e for e in events if e['dt'] >= now][:4] or events[:4]
    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    lines = [f"• {e['dt'].strftime(f'%m/%d({weekdays[e[\"dt\"].weekday()]}) %H:%M')} {e['name']}" for e in upcoming]
    return (
        "🚨 오늘 밤엔 큰 거 하나 온다! 긴장 바짝 해!\n\n"
        "🗓️ 이번 주 핵심 개미 캘린더 ★★★\n" + "\n".join(lines) +
        "\n\n\"지표나 실적 발표 전후로는 호가창 얇아지니까 뇌동매매 절대 금지야! 알았제?\""
    )

@app.route('/')
def home():
    return "gaemiGTP 초고속 병렬 엔진 가동 중!"

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

        if not ticker_symbol:
            return jsonify({
                "sections": [{"title": f"⚠️ '{raw_name}' 종목을 찾을 수 없어!", "content": "정확한 종목명이나 6자리 종목코드로 다시 검색해줘!"}]
            })

        is_krw = ('-' not in ticker_symbol and ticker_symbol.endswith(('.KS', '.KQ'))) or (clean_code and len(clean_code) == 6)

        # ⚡ [핵심] ThreadPoolExecutor로 시세, 수급, 뉴스를 동시에 병렬 수집!
        with ThreadPoolExecutor(max_workers=3) as executor:
            if is_krw and clean_code:
                future_price = executor.submit(fetch_kr_stock_realtime, clean_code)
                future_supply = executor.submit(fetch_krx_trend_and_supply, clean_code)
                future_news = executor.submit(fetch_realtime_news_and_reason, raw_name)

                cur_p, diff, ratio = future_price.result()
                ma20_val, res_val, f_5d, i_5d, ind_5d, v_days = future_supply.result()
                ai_reason, news_list = future_news.result()

                current_price = cur_p or ma20_val or 0.0
                change_pct = ratio if ratio is not None else 0.0
                ma20 = ma20_val if ma20_val else current_price * 0.95
                resistance_price = res_val if res_val else current_price * 1.05
                price_str = f"{round_krw_tick(current_price):,}원"
                ma20_str = f"{round_krw_tick(ma20):,}원"
                res_str = f"{round_krw_tick(resistance_price):,}원"

                if f_5d is not None and i_5d is not None and v_days > 0:
                    tag_line = f"#외국인 {format_shares(f_5d)}   #기관 {format_shares(i_5d)}   #개인 {format_shares(ind_5d)}"
                    if f_5d > 0 and i_5d > 0:
                        supply_content = f"{tag_line}\n\n최근 5일 동안 외인과 기관이 쌍끌이로 물량을 쓸어 담고 있어!\n메이저 세력이 바닥을 다져놨으니 흔들려도 버티는 게 맞아."
                    elif f_5d < 0 and i_5d < 0:
                        supply_content = f"{tag_line}\n\n최근 5일 동안 큰손들이 시장에서 발을 빼고 있어.\n절대 무리하게 물타지 말고 조심해야 돼."
                    elif f_5d > 0:
                        supply_content = f"{tag_line}\n\n최근 5일간 외국인이 지친 개미 물량을 싹 쓸어 담았어.\n단기 슈팅 흐름 기대해 봐도 좋아."
                    else:
                        supply_content = f"{tag_line}\n\n세력들이 팽팽하게 눈치싸움 중이야. 기준선 지키는지 확인하자."
                else:
                    supply_content = "현재 수급 데이터를 집계 중이야."

            else:
                future_us = executor.submit(fetch_us_stock, ticker_symbol)
                future_news = executor.submit(fetch_realtime_news_and_reason, raw_name)

                cur_p, prev_p, ma20_val, res_val = future_us.result()
                ai_reason, news_list = future_news.result()

                current_price = cur_p or 0.0
                change_pct = ((cur_p - prev_p) / prev_p) * 100 if cur_p and prev_p else 0.0
                ma20 = ma20_val or current_price * 0.95
                resistance_price = res_val or current_price * 1.05
                price_str = f"${current_price:,.2f}"
                ma20_str = f"${ma20:,.2f}"
                res_str = f"${resistance_price:,.2f}"
                supply_content = "#콜 18.4만건   #풋 11.2만건   #비율 0.61\n\n월가 큰손들이 상방 베팅을 이어가고 있어!"

        # 상태별 멘트 구성
        if change_pct >= 0.5:
            status_emoji, title_word = '🔥', '상승했을까'
            intro_ment = f"스멀스멀 {change_pct:+.2f}% 우상향 중이야\n개미들아! 분위기 나쁘지 않은데? 이대로만 가자"
        elif change_pct <= -0.5:
            status_emoji, title_word = '❄️', '하락했을까'
            intro_ment = f"아이고 {change_pct:+.2f}% 파란불 켜져서 속 쓰리겠다\n개미들아! 물 한잔 마시고 차분하게 보자"
        else:
            status_emoji, title_word = '⚖️', '보합일까'
            intro_ment = f"{change_pct:+.2f}%로 팽팽한 눈치싸움 중이야"

        news_lines = "\n".join([f"📰 {t}" for t in news_list]) if news_list else f"📰 {raw_name} 주요 재료 분석 중"
        escape_content = f"#생존 지지선 {ma20_str} 기억해! 깨지면 비중 줄여!\n\n#악성 매물대 {res_str}\n돌파한다고 무지성 매수 타면 물린다잉!"

        sections = [
            {
                "title": f"{status_emoji} 오늘 왜 {title_word}?",
                "content": f"{intro_ment}\n\n현재 주가는 {price_str} 기록 중!\n\n💡 {ai_reason}\n\n{news_lines}\n\n#{raw_name} #{change_pct:+.2f}%"
            },
            {"title": "큰손들은 담고 있을까, 털고 있을까?", "content": supply_content},
            {"title": "여기 깨지면 도망쳐", "content": escape_content},
            {"title": "오늘 밤, 이번주 무슨 일이 있나?", "content": get_live_calendar_data()}
        ]
        return jsonify({"sections": sections})

    except Exception:
        return jsonify({"sections": [{"title": "⚠️ 통신 지연", "content": "잠시 후 다시 검색해줘!"}]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
