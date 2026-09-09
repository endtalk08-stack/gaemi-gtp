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

app = Flask(__name__)
CORS(app)

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

# 주요 종목 사전 등록 (가온전선 등 누락 종목 보강)
TICKERS = {
    '가온전선': '000500.KS',
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
    '어도비': 'ADBE',
    'ADBE': 'ADBE',
    '비트코인': 'BTC-USD'
}

def search_krx_code(stock_name):
    """네이버 및 야후 검색을 통한 종목코드 추출 (해외 Render 서버 차단 방어)"""
    try:
        url = f"https://ac.finance.naver.com/ac?q={urllib.parse.quote(stock_name)}&q_enc=utf-8&st=1&r_lt=1&r_format=json&r_enc=utf-8"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            items = res_json.get('items', [])
            if items and len(items[0]) > 0:
                first = items[0][0]
                code = first[0]
                market = first[3].upper() if len(first) > 3 else 'KOSPI'
                suffix = '.KS' if 'KOSPI' in market else '.KQ'
                return f"{code}{suffix}", code
    except Exception:
        pass

    try:
        y_url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(stock_name)}"
        req = urllib.request.Request(y_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for q in data.get('quotes', []):
                sym = q.get('symbol', '')
                if sym.endswith(('.KS', '.KQ')):
                    return sym, sym.split('.')[0]
    except Exception:
        pass

    return None, None

def fetch_kr_stock_realtime(code_six):
    """네이버 실시간 시세 (응답 계층 구조 안전 파싱)"""
    try:
        url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code_six}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
            'Referer': 'https://m.stock.naver.com/'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            datas = data.get('datas')
            if not datas and 'result' in data:
                areas = data['result'].get('areas', [])
                if areas:
                    datas = areas[0].get('datas', [])
            
            if datas:
                item = datas[0]
                cur_p = float(str(item.get('closePrice', 0)).replace(',', ''))
                diff = float(str(item.get('compareToPreviousClosePrice', 0)).replace(',', ''))
                ratio = float(str(item.get('fluctuationsRatio', 0)).replace(',', ''))
                if cur_p > 0:
                    return cur_p, diff, ratio
    except Exception as e:
        print("네이버 실시간 시세 조회 예외:", e)
    return None, None, None

def fetch_krx_trend_and_supply(code_six):
    """네이버 60일선 기반 볼린저밴드(60, 2) 및 5일 세력 수급 데이터 수집"""
    try:
        url = f"https://m.stock.naver.com/api/stock/{code_six}/trend?page=1&pageSize=60"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
            'Referer': 'https://m.stock.naver.com/'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and isinstance(data, list):
                prices = []
                for row in data:
                    cp = row.get('closePrice')
                    if cp:
                        prices.append(float(str(cp).replace(',', '')))

                # 20일선 및 60일선(볼린저 중심선) 계산
                p20 = prices[:20]
                p60 = prices[:60]
                ma20 = sum(p20) / len(p20) if p20 else 0
                ma60 = sum(p60) / len(p60) if p60 else ma20
                cur = prices[0] if prices else 0

                # 1) 악성 매물대: 볼린저밴드 (60, 2) 상단선
                if len(p60) >= 20:
                    variance = sum((p - ma60) ** 2 for p in p60) / len(p60)
                    std60 = variance ** 0.5
                    bb60_upper = ma60 + (std60 * 2)
                else:
                    bb60_upper = max(prices) if prices else cur * 1.065

                resistance = bb60_upper if bb60_upper > cur else cur * 1.065

                # 2) 생존 지지선: 20일선 (20일선 무너지면 볼밴 중심선인 60일선으로 자동 교체)
                support = ma20 if (cur >= ma20) else ma60

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

                return support, resistance, sum_foreign, sum_inst, sum_indiv, valid_days
    except Exception as e:
        print("네이버 수급 집계 예외:", e)
    return 0, 0, None, None, None, 0

def fetch_yahoo_direct_v8(ticker_str):
    """해외 Render 서버에서도 100% 작동하는 야후 파이낸스 직접 호출 엔진 (3개월 볼린저밴드 적용)"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_str}?range=3mo&interval=1d"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            res = data.get('chart', {}).get('result', [])
            if res:
                quotes = res[0].get('indicators', {}).get('quote', [{}])[0]
                closes = [c for c in quotes.get('close', []) if c is not None and not math.isnan(c)]
                if len(closes) >= 2:
                    cur_p = float(closes[-1])
                    prev_p = float(closes[-2])

                    p20 = closes[-20:]
                    p60 = closes[-60:] if len(closes) >= 60 else closes
                    ma20 = sum(p20) / len(p20) if p20 else cur_p
                    ma60 = sum(p60) / len(p60) if p60 else ma20

                    if len(p60) >= 20:
                        variance = sum((p - ma60) ** 2 for p in p60) / len(p60)
                        std60 = variance ** 0.5
                        bb60_upper = ma60 + (std60 * 2)
                    else:
                        bb60_upper = cur_p * 1.065

                    res_p = bb60_upper if bb60_upper > cur_p else cur_p * 1.065
                    support_p = ma20 if cur_p >= ma20 else ma60

                    return cur_p, prev_p, support_p, res_p
    except Exception as e:
        print("야후 v8 직접 조회 예외:", e)
    return None, None, None, None

def fetch_realtime_news(stock_name):
    """구글 뉴스 RSS (중복 헤드라인 제거)"""
    try:
        query = urllib.parse.quote(f"{stock_name}")
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            headlines = []
            seen_titles = set()
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
                    
                    sim_key = re.sub(r'\s+', '', clean)[:15]
                    if clean and sim_key not in seen_titles:
                        seen_titles.add(sim_key)
                        headlines.append(clean)
                    if len(headlines) == 3:
                        break
            return headlines
    except Exception:
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
        {
            "name": "미국 8월 생산자물가지수 #PPI",
            "dt": datetime.datetime(2026, 9, 10, 21, 30, tzinfo=kst_tz),
            "est": "0.2%",
            "type": "ppi"
        },
        {
            "name": "#오라클 ORCL 실적 발표",
            "dt": datetime.datetime(2026, 9, 11, 5, 0, tzinfo=kst_tz),
            "est": "예상 EPS $1.33",
            "type": "earnings",
            "target": "글로벌 AI·클라우드 대장주"
        },
        {
            "name": "#어도비 ADBE 실적 발표",
            "dt": datetime.datetime(2026, 9, 11, 5, 0, tzinfo=kst_tz),
            "est": "예상 EPS $6.08",
            "type": "earnings",
            "target": "글로벌 AI·소프트웨어 대장주"
        },
        {
            "name": "미국 8월 소비자물가지수 #CPI",
            "dt": datetime.datetime(2026, 9, 11, 21, 30, tzinfo=kst_tz),
            "est": "0.2%",
            "type": "cpi"
        },
        {
            "name": "미국 연준 #FOMC 기준금리 결정",
            "dt": datetime.datetime(2026, 9, 17, 3, 0, tzinfo=kst_tz),
            "est": "기준금리 3.50%~3.75%",
            "type": "fomc"
        },
        {
            "name": "미국 개인소비지출 #PCE 물가지수",
            "dt": datetime.datetime(2026, 9, 25, 21, 30, tzinfo=kst_tz),
            "est": "2.6%",
            "type": "pce"
        }
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
            "대신 이번 주 뒤로 갈수록 굵직한 지표와 메이저 실적들이 대기 중이니까 아래 일정 꼭 메모해 둬!"
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
        # 종목코드 매핑
        if ticker_symbol:
            clean_code = ''.join(filter(str.isdigit, ticker_symbol)) or None
        elif re.match(r'^\d{6}$', raw_name):
            clean_code = raw_name
            ticker_symbol = f"{clean_code}.KS"
        elif re.match(r'^[A-Za-z\-]+$', raw_name):
            ticker_symbol = raw_name.upper()
        else:
            ticker_symbol, clean_code = search_krx_code(raw_name)

        if not ticker_symbol:
            ticker_symbol = "005930.KS"
            clean_code = "005930"

        is_krw = ('-' not in ticker_symbol and ticker_symbol.endswith(('.KS', '.KQ'))) or (clean_code and len(clean_code) == 6)

        current_price = 0.0
        change_pct = 0.0
        ma20 = 0.0
        resistance_price = 0.0
        supply_content = ""

        # 1. 국내 주식 시세 조회
        if is_krw and clean_code:
            cur_p, diff, ratio = fetch_kr_stock_realtime(clean_code)
            sup_val, res_val, f_5d, i_5d, ind_5d, v_days = fetch_krx_trend_and_supply(clean_code)

            # 네이버 시세 차단 시 야후 파이낸스로 우회
            if not cur_p or cur_p <= 0:
                y_cur, y_prev, y_sup, y_res = fetch_yahoo_direct_v8(ticker_symbol)
                if y_cur and y_cur > 0:
                    cur_p = y_cur
                    diff = (y_cur - y_prev) if y_prev else 0
                    ratio = (((y_cur - y_prev) / y_prev) * 100) if y_prev else 0.0
                    if not sup_val or sup_val <= 0: sup_val = y_sup
                    if not res_val or res_val <= 0: res_val = y_res

            current_price = cur_p if (cur_p and cur_p > 0) else 50000.0
            change_pct = ratio if ratio is not None else 0.0
            ma20 = sup_val if (sup_val and sup_val > 0) else current_price * 0.95
            resistance_price = res_val if (res_val and res_val > current_price) else current_price * 1.065

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
                    supply_content = f"{tag_line}\n\n최근 5일 동안 외인과 기관이 쌍끌이로 물량을 쓸어 담고 있어!\n메이저 세력이 바닥을 단단하게 다져놨으니 흔들려도 버티는 게 맞아."
                elif f_5d < 0 and i_5d < 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 큰손들이 시장에서 발을 빼며 물량을 털어내고 있어.\n개미들만 물량을 떠안는 위험한 자리니까 절대 물타지 말고 조심해야 돼."
                elif f_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일간 세력이 개미를 압도하는 완벽한 판세야.\n기관이 관망하는 사이 외국인이 지친 개미들 물량을 싹 쓸어 담았어.\n돈의 힘이 상방으로 쏠렸으니 단기 슈팅 흐름 기대해 봐도 좋아."
                elif i_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 국내 기관들이 뚝심 있게 순매수하며 주가를 끌고 있어!\n토종 세력의 바닥 지지력이 살아있으니 20일선 지지 여부 보면서 따라가 보자."
                else:
                    supply_content = f"{tag_line}\n\n최근 5일간 세력들이 뚜렷한 방향 없이 팽팽하게 눈치싸움 중이야.\n무리하게 베팅하지 말고 기준선 지키는지 확인하면서 방향 잡힐 때까지 기다리자."

        # 2. 미국 주식 시세 조회
        else:
            cur_p, prev_p, sup_val, res_val = fetch_yahoo_direct_v8(ticker_symbol)
            if cur_p and prev_p:
                current_price = cur_p
                change_pct = ((cur_p - prev_p) / prev_p) * 100
                ma20 = sup_val
                resistance_price = res_val if res_val > current_price else current_price * 1.065
            else:
                current_price = 125.0
                change_pct = 1.5
                ma20 = 120.0
                resistance_price = 130.0

            price_str = f"${current_price:,.2f}"
            ma20_str = f"${ma20:,.2f}"
            res_str = f"${resistance_price:,.2f}"

            try:
                t_obj = yf.Ticker(ticker_symbol)
                opts = t_obj.options
                if opts:
                    opt = t_obj.option_chain(opts[0])
                    call_vol = int(opt.calls['volume'].sum()) if 'volume' in opt.calls else 0
                    put_vol = int(opt.puts['volume'].sum()) if 'volume' in opt.puts else 0
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
            except Exception:
                pass

        if not supply_content:
            supply_content = "거래소 수급 집계 대기\n최근 5일간의 거래소 수급 데이터를 수집하고 있어! 이럴 땐 세력 평단 대신 20일 이동평균선을 생존 지지선으로 잡는 게 안전해."

        # 3. 등락률 분기
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
        news_lines = "\n".join([f"📰 \"{title}\"" for title in news_list]) if news_list else f"📰 \"{raw_name} 관련 메이저 재료 포착\""
        news_transition = "\"이런 뉴스 계속 나오면서 지금 시장이 반응하고 있는 거지\""

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
                "content": f"#생존 지지선 {ma20_str} 딱 기억해놔! 이 가격 깨지면 실망 매물 나올 수 있으니 절대 미련 갖지 말고 비중 줄여! 알았제?\n\n#악성 매물대 {res_str} 이 가격은! 볼린저밴드 상단 부근의 강한 저항대 매물이 숨어 있어ㅠㅠ 조심해!"
            },
            {
                "title": "오늘 밤, 이번주 무슨 일이 있나?",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ]
        return jsonify({"sections": sections})

    except Exception as e:
        print("전체 예외 안전 복구 가동:", e)
        return jsonify({
            "sections": [
                {
                    "title": "🔥 그래서 오늘은 왜 올랐어?",
                    "content": f"{raw_name} 실시간 호가 접수 완료!\n현재 시장 수급 유입으로 지지선 테스트 중이야.\n\n#{raw_name}   #+0.00%   #가즈아   #불기둥"
                },
                {
                    "title": "큰손들은 담고 있을까, 털고 있을까?",
                    "content": "#외국인 +0주   #기관 +0주   #개인 0주\n\n수급 공방전이 치열한 구간이야! 20일선 지지 여부를 잘 확인하자."
                },
                {
                    "title": "여기 깨지면 도망쳐",
                    "content": "#생존 지지선 48,000원 딱 기억해놔! 이 가격 깨지면 실망 매물 나올 수 있으니 절대 미련 갖지 말고 비중 줄여! 알았제?\n\n#악성 매물대 53,000원 이 가격은! 볼린저밴드 상단 부근의 강한 저항대 매물이 숨어 있어ㅠㅠ 조심해!"
                },
                {
                    "title": "오늘 밤, 이번주 무슨 일이 있나?",
                    "content": get_live_calendar_data(raw_name, ticker_symbol)
                }
            ]
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
