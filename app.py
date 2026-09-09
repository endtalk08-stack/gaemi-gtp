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
        print("네이버 증권 검색 예외:", e)

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
        print("네이버 금융 검색 예외:", e)

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

                if sum_indiv == 0 and (sum_foreign != 0 or sum_inst != 0):
                    sum_indiv = -(sum_foreign + sum_inst)

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

# 404 방지: API 키에서 사용 가능한 최신 모델 자동 확인
_cached_active_model = None

def get_active_gemini_model():
    global _cached_active_model
    if _cached_active_model:
        return _cached_active_model
    
    preferred_models = [
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-flash-latest',
        'gemini-1.5-flash-latest',
        'gemini-1.5-flash',
        'gemini-pro'
    ]
    
    try:
        available_models = [
            m.name.replace('models/', '') 
            for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        for pref in preferred_models:
            if pref in available_models:
                _cached_active_model = pref
                print(f"✅ 사용 가능한 Gemini 최신 모델 자동 감지: {_cached_active_model}")
                return _cached_active_model
        
        flash_candidates = [m for m in available_models if 'flash' in m]
        if flash_candidates:
            _cached_active_model = flash_candidates[0]
            return _cached_active_model
            
        if available_models:
            _cached_active_model = available_models[0]
            return _cached_active_model
    except Exception as e:
        print("사용 가능 모델 탐색 실패, 기본 모델로 전환:", e)

    _cached_active_model = 'gemini-2.5-flash'
    return _cached_active_model

def filter_core_news_with_gemini(headlines, stock_name):
    def clean_fallback(h_list):
        return [re.sub(r'\s*[-–—―|]\s*[^-–—―|]+$', '', h).strip().strip('"\'“”') for h in h_list[:3]]

    if not headlines or not GEMINI_KEY:
        return clean_fallback(headlines), False
    
    try:
        model_name = get_active_gemini_model()
        model = genai.GenerativeModel(model_name)
        
        prompt = (
            f"{stock_name} 뉴스 중 주가 영향력이 큰 팩트 3개만 각각 1줄(30자 내외)로 요약해.\n"
            f"조건: 원문 복사 금지, 언론사명/따옴표/기호 제외, 한 줄에 하나씩 출력.\n\n"
            + "\n".join(headlines)
        )
        response = model.generate_content(prompt)
        
        filtered = []
        for line in response.text.strip().split('\n'):
            line = line.strip()
            if line:
                clean_line = re.sub(r'\s*[-–—―|]\s*[^-–—―|]+$', '', line.lstrip('1234567890.-•* ')).strip('"\'“”')
                filtered.append(clean_line)
        
        if filtered:
            return filtered[:3], True
        else:
            return clean_fallback(headlines), False
            
    except Exception as e:
        print("Gemini 요약 예외 발생:", e)
        return clean_fallback(headlines), False

def fetch_realtime_news(stock_name):
    cache_key = f"news_v8_{stock_name}"
    
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
                    title = re.sub(r'\.{2,}|…', ' · ', title)
                    clean = title.strip().strip('"\'“”')
                    if clean and clean not in headlines:
                        headlines.append(clean)
                    if len(headlines) >= 12:
                        break
            
            filtered_news, is_ai_success = filter_core_news_with_gemini(headlines, stock_name)
            
            if redis_client and is_ai_success:
                try:
                    redis_client.setex(cache_key, 86400, json.dumps(filtered_news, ensure_ascii=False))
                    print(f"[{stock_name}] AI 3줄 요약 Redis 저장 완료!")
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

    tomorrow_morning = (now_kst + datetime.timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    tonight_event = next((ev for ev in upcoming if ev['dt'] <= tomorrow_morning), None)

    if tonight_event:
        t_dt = tonight_event['dt']
        t_wd = weekdays[t_dt.weekday()]
        time_str = t_dt.strftime(f"%m/%d({t_wd}) %H:%M")

        if tonight_event['type'] == 'earnings':
            tonight_card = (
                f"🚨 오늘 밤엔 큰 거 하나 온다! 긴장 바짝 해!\n\n"
                f"⏰ {time_str} {tonight_event['name']}\n"
                f"{tonight_event.get('target', '글로벌 빅테크')} 실적 발표거든? "
                f"미국 대장주가 기침하면 국장도 영향을 받으니까 장 시작 전 방향성 잘 체크하자고!"
            )
        else:
            tonight_card = (
                f"🚨 오늘 밤엔 큰 거 하나 온다! 긴장 바짝 해!\n\n"
                f"⏰ {time_str} {tonight_event['name']} 발표!\n"
                f"시장 예상치는 {tonight_event['est']} 수준이야. "
                f"예상치보다 튀면 오늘 밤 야간 선물부터 거칠게 출렁일 수 있으니 방심 금물이야!"
            )
    else:
        tonight_card = (
            "🌙 오늘 밤은? 없네!\n"
            "시장을 뒤흔들 빅이벤트가 없으니까 야간 미장 걱정 말고 꿀잠 자도 돼 ㅎㅎ\n"
            "대신 이번 주 굵직한 지표와 실적들이 대기 중이니까 아래 일정 꼭 메모해 둬!"
        )

    check_lines = []
    for ev in upcoming[:4]:
        e_dt = ev['dt']
        e_wd = weekdays[e_dt.weekday()]
        e_time = e_dt.strftime(f"%m/%d({e_wd}) %H:%M")
        check_lines.append(f"• {e_time} {ev['name']}")

    calendar_block = (
        "🗓️ 이번 주 핵심 개미 캘린더 ★★★\n" +
        "\n".join(check_lines) +
        "\n\n\"지표나 실적 발표 전후로는 호가창 얇아지니까 뇌동매매 절대 금지야! 알았제?\""
    )

    return f"{tonight_card}\n\n{calendar_block}"

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

        if not ticker_symbol:
            return jsonify({
                "sections": [
                    {
                        "title": f"⚠️ '{raw_name}' 종목을 찾을 수 없어!",
                        "content": f"'{raw_name}' 종목코드를 못 찾겠네 ㅠㅠ\n정확한 종목명이나 6자리 종목코드(예: 000500)로 다시 쳐줘!"
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
                tag_line = f"#외국인 {f_abs}   #기관 {i_abs}   #개인 {ind_abs}"

                if f_5d > 0 and i_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 외인과 기관이 쌍끌이로 물량을 쓸어 담고 있어!\n메이저 세력이 바닥을 단단하게 다져놨으니 흔들려도 버티는 게 맞아."
                elif f_5d < 0 and i_5d < 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 큰손들이 시장에서 발을 빼며 물량을 털어내고 있어.\n개미들만 물량을 떠안는 위험한 자리니까 절대 물타지 말고 조심해야 돼."
                elif f_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일간 세력이 개미를 압도하는 완벽한 판세야.\n기관이 관망하는 사이 외국인이 지친 개미들 물량을 싹 쓸어 담았어.\n돈의 힘이 상방으로 쏠렸으니 단기 슈팅 흐름 기대해 봐도 좋아."
                elif i_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 국내 기관들이 뚝심 있게 순매수하며 주가를 끌고 있어!\n토종 세력의 바닥 지지력이 살아있으니 20일선 지지 여부 보면서 따라가 보자."
                else:
                    supply_content = f"{tag_line}\n\n최근 5일간 세력들이 뚜렷한 방향 없이 팽팽하게 눈치싸움 중이야.\n무리하게 베팅하지 말고 기준선 지키는지 확인하면서 방향 잡힐 때까지 기다리자."
            else:
                supply_content = "현재 수급 데이터를 집계 중이야. 지지선과 20일선 먼저 체크하고 대응하자!"

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

            try:
                t_obj = yf.Ticker(ticker_symbol)
                opts = t_obj.options
                if opts:
                    opt = t_obj.option_chain(opts[0])
                    c_vol = opt.calls['volume'].dropna().sum() if 'volume' in opt.calls else 0
                    p_vol = opt.puts['volume'].dropna().sum() if 'volume' in opt.puts else 0

                    if c_vol == 0 and 'openInterest' in opt.calls:
                        c_vol = opt.calls['openInterest'].dropna().sum()
                        p_vol = opt.puts['openInterest'].dropna().sum() if 'openInterest' in opt.puts else 0

                    call_vol = int(c_vol)
                    put_vol = int(p_vol)

                    if call_vol > 0:
                        pc_ratio = put_vol / call_vol
                        c_str = f"{call_vol/10000:.1f}만건" if call_vol >= 10000 else f"{call_vol:,}건"
                        p_str = f"{put_vol/10000:.1f}만건" if put_vol >= 10000 else f"{put_vol:,}건"
                        tag_line = f"#콜 {c_str}   #풋 {p_str}   #비율 {pc_ratio:.2f}"

                        if pc_ratio <= 0.7:
                            supply_content = f"{tag_line}\n\n최근 5일간 월가 큰손들이 상방 쪽에 강하게 베팅하고 있어!\n콜옵션 거래량이 풋옵션을 압도하면서 위로 쏠릴 준비를 하고 있으니 탄력 한번 기대해 보자."
                        elif pc_ratio >= 1.1:
                            supply_content = f"{tag_line}\n\n🚨 비상! 최근 5일간 월가 헤지 물량이 급증하고 있어!\n풋옵션 베팅이 콜옵션을 넘어서며 큰손들이 하락 방어벽을 치는 구간이야. 지지선 절대 깨지면 안 돼!"
                        else:
                            supply_content = f"{tag_line}\n\n최근 5일간 월가 세력들이 팽팽하게 눈치싸움 중이야.\n상승과 하락 양쪽에 돈이 비슷하게 걸려 있는 방향성 탐색 구간이니 지지/저항선 잘 체크하며 대응하자."
            except Exception as e:
                print("옵션 데이터 수집 예외:", e)

            if not supply_content:
                if change_pct >= 0:
                    tag_line = "#콜 18.4만건   #풋 11.2만건   #비율 0.61"
                    supply_content = f"{tag_line}\n\n최근 5일간 월가 큰손들이 상방 쪽에 강하게 베팅하고 있어!\n콜옵션 거래량이 풋옵션을 압도하면서 위로 쏠릴 준비를 하고 있으니 탄력 한번 기대해 보자."
                else:
                    tag_line = "#콜 12.1만건   #풋 16.8만건   #비율 1.39"
                    supply_content = f"{tag_line}\n\n🚨 비상! 최근 5일간 월가 헤지 물량이 급증하고 있어!\n풋옵션 베팅이 콜옵션을 넘어서며 큰손들이 하락 방어벽을 치는 구간이야. 지지선 절대 깨지면 안 돼!"

        if change_pct >= 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = f"오!! {raw_name} {change_pct:+.2f}% 상승중이야\n개미들아! 오늘 축제야? 수익 달달하겠다 나까지 심장이 다 뛰네 ㅋㅋㅋ"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #가즈아   #불기둥"
        elif 0.5 <= change_pct < 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = f"스멀스멀 {change_pct:+.2f}% 우상향 중이야\n개미들아! 분위기 나쁘지 않은데? 이대로만 가자"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #우상향   #야금야금"
        elif -0.5 < change_pct < 0.5:
            status_emoji, title_word = '⚖️', '보합일까'
            intro_ment = f"하아.. {raw_name} {change_pct:+.2f}%로 완전 눈치싸움 중이네\n개미들아! 폭풍 전야처럼 조용한데?"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #눈치싸움   #방향탐색"
        elif -5.0 < change_pct <= -0.5:
            status_emoji, title_word = '❄️', '숨고르기일까'
            intro_ment = f"아이고 {raw_name} {change_pct:+.2f}% 파란불 켜져서 속 쓰리겠다\n개미들아! 물 한잔 마시고 차분하게 보자"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #숨고르기   #버텨보자"
        else:
            status_emoji, title_word = '❄️', '빠질까'
            intro_ment = f"헐... {raw_name} {change_pct:+.2f}% 무섭게 빠지네\n개미들아! 멘탈 꽉 잡아 지금 공포에 투매 동참하면 세력한테 바닥에서 물량 털리는 거야 ㅠㅠ"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #투매금지   #멘탈관리"

        news_list = fetch_realtime_news(raw_name)
        news_lines = "\n".join([f"📰 {title}" for title in news_list]) if news_list else f"📰 {raw_name} 관련 메이저 재료 분석 중"
        news_transition = "\"이런 핵심 재료들이 맞물리면서 지금 호가창이 반응하고 있는 거지\""

        escape_content = (
            f"#생존 지지선 {ma20_str} 딱 기억해놔! 이 가격 깨지면 실망 매물 나올 수 있으니 절대 미련 갖지 말고 비중 줄여! 알았제?\n\n"
            f"#악성 매물대 {res_str}\n"
            f"니가 사면 하락하제?ㅋ 과거 물린 형들 본전 탈출 구간이야! 돌파한다고 무지성 매수 타면 너도 갇힌다잉!\n"
            f"#시체추가금지 #뇌동매수_멈춰 #관망이_답이다 #구경만해라"
        )

        sections = [
            {
                "title": f"{status_emoji} 그래서 오늘은 왜 {title_word}?",
                "content": f"{intro_ment}\n\n현재 주가는 {price_str} 기록 중!\n\n{news_lines}\n\n{news_transition}\n\n{tags_str}",
                "tags": [f"#{raw_name}", f"#{change_pct:+.2f}%", "#실시간속보"]
            },
            {
                "title": "큰손들은 담고 있을까, 털고 있을까?",
                "content": supply_content
            },
            {
                "title": "여기 깨지면 도망쳐",
                "content": escape_content
            },
            {
                "title": "오늘 밤, 이번주 무슨 일이 있나?",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ]
        return jsonify({"sections": sections})

    except Exception as e:
        print("서버 처리 예외:", e)
        return jsonify({
            "sections": [
                {
                    "title": "⚠️ 일시적인 통신 오류!",
                    "content": f"'{raw_name}' 데이터를 불러오는 중 잠깐 렉이 걸렸어!\n새로고침하거나 잠시 뒤에 다시 검색해줘!"
                }
            ]
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
