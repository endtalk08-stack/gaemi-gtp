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

FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '').strip().strip('\'"')

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
            for item in items:
                title_el = item.find('title')
                if title_el is not None and title_el.text:
                    title = title_el.text
                    title = re.sub(r'\[.*?\]', '', title)
                    title = re.sub(r'<[^>]+>', '', title)
                    title = re.sub(r'\s*[-–—―|]\s*[^-–—―|]+$', '', title)
                    title = re.sub(r'\s*[-–—―|]\s*[^-–—―|]+$', '', title)
                    title = re.sub(r'[\.…]+\s*$', '', title)
                    title = re.sub(r'\.{2,}|…', ' · ', title)
                    
                    clean = title.strip().strip('"\'“”')
                    if clean:
                        headlines.append(clean)
                    if len(headlines) == 3:
                        break
            return headlines
    except Exception:
        return []

# 네이버 모바일 정규 trend API + PC 백업 2중 수급 집계
def fetch_krx_5d_supply_demand(code_six):
    # 1차: 모바일 trend API
    try:
        url = f"https://m.stock.naver.com/api/stock/{code_six}/trend?page=1&pageSize=5"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Referer': 'https://m.stock.naver.com/'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and isinstance(data, list):
                sum_inst = 0
                sum_foreign = 0
                valid_days = 0
                for row in data:
                    frgn = row.get('foreignerPureBuyQuant') or row.get('frgnPureBuyQuant') or 0
                    insti = row.get('institutionPureBuyQuant') or row.get('instiPureBuyQuant') or 0
                    f_val = int(str(frgn).replace(',', ''))
                    i_val = int(str(insti).replace(',', ''))
                    sum_foreign += f_val
                    sum_inst += i_val
                    valid_days += 1

                if valid_days > 0:
                    sum_indiv = -(sum_inst + sum_foreign)
                    return sum_indiv, sum_foreign, sum_inst, valid_days
    except Exception as e:
        print("모바일 1차 수급 집계 예외:", e)

    # 2차: PC 웹 백업 크롤링
    try:
        headers_pc = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
            'Referer': f'https://finance.naver.com/item/main.naver?code={code_six}'
        }
        url_pc = f"https://finance.naver.com/item/frgn.naver?code={code_six}"
        req_pc = urllib.request.Request(url_pc, headers=headers_pc)
        with urllib.request.urlopen(req_pc, timeout=4) as resp:
            html = resp.read().decode('euc-kr', 'replace')
            rows = re.findall(r'<tr[^>]*>\s*<td class="tc">\s*<span class="tah p10 gray03">\d{4}\.\d{2}\.\d{2}</span>.*?</tr>', html, re.DOTALL)
            if rows:
                sum_inst = 0
                sum_foreign = 0
                valid_days = 0
                for r in rows[:5]:
                    tds = r.split('<td')
                    if len(tds) > 7:
                        inst_clean = re.sub(r'[^0-9\-]', '', tds[6])
                        foreign_clean = re.sub(r'[^0-9\-]', '', tds[7])
                        if inst_clean and foreign_clean and inst_clean != '-' and foreign_clean != '-':
                            sum_inst += int(inst_clean)
                            sum_foreign += int(foreign_clean)
                            valid_days += 1

                if valid_days > 0:
                    sum_indiv = -(sum_inst + sum_foreign)
                    return sum_indiv, sum_foreign, sum_inst, valid_days
    except Exception as e:
        print("PC 2차 수급 백업 집계 예외:", e)

    return None, None, None, 0

def fetch_us_put_call_ratio(ticker_obj):
    try:
        opts = ticker_obj.options
        if not opts:
            return None
        opt = ticker_obj.option_chain(opts[0])
        calls = opt.calls
        puts = opt.puts
        call_vol = calls['volume'].sum() if 'volume' in calls else 0
        put_vol = puts['volume'].sum() if 'volume' in puts else 0
        if call_vol == 0:
            return None
        return put_vol / call_vol
    except Exception as e:
        print("미국 옵션 수급 집계 에러:", e)
        return None

def format_shares(n):
    if n is None: return "0주"
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

# 4섹션: 2번째 카드/불릿형 + 이번 주 핵심 체크 레이아웃
def get_live_calendar_data(stock_name, ticker_symbol):
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_tz)
    
    schedule = [
        {"name": "미국 8월 소비자물가지수(CPI)", "dt": datetime.datetime(2026, 9, 11, 21, 30, tzinfo=kst_tz), "est": "0.2%", "star": "★★★"},
        {"name": "미국 연준 FOMC 기준금리 결정", "dt": datetime.datetime(2026, 9, 17, 3, 0, tzinfo=kst_tz), "est": "기준금리 3.50%~3.75%", "star": "★★★"},
        {"name": "미국 생산자물가지수(PPI)", "dt": datetime.datetime(2026, 9, 18, 21, 30, tzinfo=kst_tz), "est": "0.2%", "star": "★★☆"},
        {"name": "미국 개인소비지출(PCE) 물가지수", "dt": datetime.datetime(2026, 9, 25, 21, 30, tzinfo=kst_tz), "est": "2.6%", "star": "★★★"},
        {"name": "미국 9월 비농업 고용보고서(NFP)", "dt": datetime.datetime(2026, 10, 2, 21, 30, tzinfo=kst_tz), "est": "15만 건", "star": "★★★"},
        {"name": "미국 9월 소비자물가지수(CPI)", "dt": datetime.datetime(2026, 10, 14, 21, 30, tzinfo=kst_tz), "est": "시장 전망치 대기", "star": "★★★"},
        {"name": "미국 연준 FOMC 기준금리 결정", "dt": datetime.datetime(2026, 10, 29, 3, 0, tzinfo=kst_tz), "est": "금리 추가 인하 여부 촉각", "star": "★★★"}
    ]

    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    upcoming = [ev for ev in schedule if ev['dt'] >= now_kst]

    main_card = ""
    if upcoming:
        first = upcoming[0]
        f_dt = first['dt']
        f_wd = weekdays[f_dt.weekday()]
        time_str = f_dt.strftime(f"%m/%d({f_wd}) %H:%M")
        main_card = f"⏰ {time_str} | {first['name']} 발표\n• 시장 예상치: {first['est']}\n• 개미 행동요령: 발표 직후 야간 선물 출렁일 수 있으니 주의"
    else:
        main_card = "⏰ 현재 주요 매크로 일정 대기 중\n• 개미 행동요령: 개별 종목 수급과 지지선 방어에 집중하자"

    # 기업 실적 카드
    earnings_card = ""
    today = datetime.date.today()
    earn_start = (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    earn_end = (today + datetime.timedelta(days=30)).strftime('%Y-%m-%d')

    if FINNHUB_KEY:
        is_us_stock = bool(re.match(r'^[A-Za-z]+$', ticker_symbol))
        if is_us_stock:
            try:
                url = f"https://finnhub.io/api/v1/calendar/earnings?from={earn_start}&to={earn_end}&symbol={ticker_symbol}&token={FINNHUB_KEY}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    earnings_list = data.get('earningsCalendar', [])
                    if earnings_list:
                        item = earnings_list[0]
                        act = item.get('epsActual')
                        est = item.get('epsEstimate')
                        date_str = item.get('date', '')
                        kr_label = US_KOREAN_NAMES.get(ticker_symbol, stock_name)
                        if act is not None and est is not None:
                            diff = act - est
                            status = "어닝 서프라이즈" if diff >= 0 else "실적 쇼크"
                            earnings_card = f"🏢 최근 발표 | {kr_label} 실적\n• 결과: EPS ${act:.2f} (예상치 ${est:.2f}) - {status}\n• 개미 행동요령: 실적 결과에 따른 단기 방향성 확인 필수"
                        elif est is not None:
                            earnings_card = f"🏢 {date_str} | {kr_label} 실적 발표\n• 예상치: EPS ${est:.2f}\n• 개미 행동요령: 대장주 실적이라 변동성 커질 수 있으니 조심"
            except Exception:
                pass
        else:
            for theme, chain in THEME_CHAIN.items():
                if stock_name in chain['kr_kids']:
                    for boss in chain['us_boss']:
                        boss_event = check_us_boss_earnings(boss)
                        if boss_event:
                            boss_date = boss_event.get('date', '')
                            kr_boss_name = US_KOREAN_NAMES.get(boss, boss)
                            earnings_card = f"🏢 {boss_date} | {kr_boss_name} 실적 발표\n• 테마: {theme} 글로벌 대장주\n• 개미 행동요령: 대장주 실적에 따라 국내 관련주 동반 변동성 조심"
                            break
                    if earnings_card: break

    # 이번 주 핵심 체크 리스트 (3개)
    check_lines = []
    for ev in upcoming[:3]:
        e_dt = ev['dt']
        e_wd = weekdays[e_dt.weekday()]
        e_time = e_dt.strftime(f"%m/%d({e_wd}) %H:%M")
        check_lines.append(f"🗓️ {e_time} {ev['name']} {ev['star']}")

    check_block = "이번 주 핵심 체크 (★★★)\n" + "\n".join(check_lines) if check_lines else ""

    sections = [main_card]
    if earnings_card:
        sections.append(earnings_card)
    if check_block:
        sections.append(check_block)

    return "\n\n".join(sections)

@app.route('/')
def home():
    return "gaemiGTP 대화형 수급 & 리포트 엔진 가동 중!"

@app.route('/analyze', methods=['GET'])
def analyze():
    raw_name = request.args.get('stock', 'SK하이닉스').strip()
    ticker_symbol = TICKERS.get(raw_name)
    clean_code = None
    hist = None

    try:
        if ticker_symbol:
            clean_code = ''.join(filter(str.isdigit, ticker_symbol))
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="1mo")
        elif re.match(r'^\d{6}$', raw_name):
            clean_code = raw_name
            t_ks = yf.Ticker(f"{clean_code}.KS")
            h_ks = t_ks.history(period="1mo")
            if not h_ks.empty:
                ticker, hist, ticker_symbol = t_ks, h_ks, f"{clean_code}.KS"
            else:
                t_kq = yf.Ticker(f"{clean_code}.KQ")
                h_kq = t_kq.history(period="1mo")
                if not h_kq.empty:
                    ticker, hist, ticker_symbol = t_kq, h_kq, f"{clean_code}.KQ"
        elif re.match(r'^[A-Za-z\-]+$', raw_name):
            ticker_symbol = raw_name.upper()
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="1mo")
        else:
            ticker_symbol, clean_code = search_krx_code(raw_name)
            if ticker_symbol:
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(period="1mo")

        if hist is None or hist.empty:
            raise ValueError("주가 데이터 조회 실패")

        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) >= 2 else current_price
        change_pct = ((current_price - prev_close) / prev_close) * 100
        ma20 = hist['Close'].mean()

        # 최근 1개월 최대 거래량 터진 날의 종가를 악성 매물대 가격으로 산출
        if 'Volume' in hist.columns and hist['Volume'].sum() > 0:
            max_vol_date = hist['Volume'].idxmax()
            resistance_price = hist.loc[max_vol_date, 'Close']
        else:
            resistance_price = hist['High'].max()

        is_krw = ('-' not in ticker_symbol and ticker_symbol.endswith(('.KS', '.KQ')))
        
        if is_krw:
            clean_price = round_krw_tick(current_price)
            clean_ma20 = round_krw_tick(ma20)
            clean_res = round_krw_tick(resistance_price)
            price_str = f"{clean_price:,}원"
            ma20_str = f"{clean_ma20:,}원"
            res_str = f"{clean_res:,}원"
        else:
            price_str = f"${current_price:,.2f}"
            ma20_str = f"${ma20:,.2f}"
            res_str = f"${resistance_price:,.2f}"

        # 1섹션: 5단계 멘트
        if change_pct >= 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = f"오!! {raw_name} {change_pct:+.2f}% 상승중이야\n개미들아! 오늘 축제야? 수익 달달하겠다 나까지 심장이 다 뛰네 ㅋㅋㅋ"
        elif 0.5 <= change_pct < 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = f"스멀스멀 {change_pct:+.2f}% 우상향 중이야\n개미들아! 분위기 나쁘지 않은데? 이대로만 가자"
        elif -0.5 < change_pct < 0.5:
            status_emoji, title_word = '⚖️', '보합일까'
            intro_ment = f"하아.. {raw_name} {change_pct:+.2f}%로 완전 눈치싸움 중이네\n개미들아! 폭풍 전야처럼 조용한데?"
        elif -5.0 < change_pct <= -0.5:
            status_emoji, title_word = '❄️', '숨고르기일까'
            intro_ment = f"아이고 {raw_name} {change_pct:+.2f}% 파란불 켜져서 속 쓰리겠다\n개미들아! 물 한잔 마시고 차분하게 보자"
        else:
            status_emoji, title_word = '❄️', '빠질까'
            intro_ment = f"헐... {raw_name} {change_pct:+.2f}% 무섭게 빠지네\n개미들아! 멘탈 꽉 잡아 지금 공포에 투매 동참하면 세력한테 바닥에서 물량 털리는 거야 ㅠㅠ"

        news_list = fetch_realtime_news(raw_name)
        if news_list:
            news_lines = "\n".join([f"📰 \"{title}\"" for title in news_list])
        else:
            news_lines = f"📰 \"{raw_name} 관련 메이저 재료 포착\""

        # 2섹션: 한국 수급 vs 미국 수급
        if is_krw:
            indiv_5d, foreign_5d, inst_5d, days = fetch_krx_5d_supply_demand(clean_code) if clean_code else (None, None, None, 0)
            if foreign_5d is not None and inst_5d is not None and days > 0:
                f_abs = format_shares(foreign_5d)
                i_abs = format_shares(inst_5d)
                ind_abs = format_shares(indiv_5d)

                if foreign_5d > 0 and inst_5d > 0:
                    supply_content = f"🔥 쌍끌이 매집 폭발!\n최근 5일간 외놈들이 {f_abs}, 기관들이 {i_abs}를 미친 듯이 쓸어 담으며 바닥을 단단히 다졌어! 메이저 세력이 개미들 물량 털어먹고 위로 쏠 준비 중이니까, 잔파도에 털리지 말고 꽉 쥐고 가자!"
                elif foreign_5d < 0 and inst_5d < 0:
                    supply_content = f"🚨 비상! 세력 양매도 폭격 경보!\n최근 5일간 외놈들이 {f_abs}, 기관들이 {i_abs}를 시장에 대놓고 패대기치고 있어! 우리 순진한 개미들만 온몸으로 물받이하고 있는 위험한 형국이니까, 절대 물타지 말고 지지선 깨지면 튀어야 해!"
                elif foreign_5d > 0:
                    supply_content = f"🛸 외놈들의 단독 방어전!\n기관들이 {i_abs} 던지면서 간을 보고 있지만, 외놈들이 {f_abs}를 묵직하게 받아내며 방어선을 치고 있어! 외놈들 매수 단가 위에서 버텨준다면 단기 반등 탄력 기대해 볼 만해."
                elif inst_5d > 0:
                    supply_content = f"🏢 여의도 기관들 연속 매집 중!\n외놈들이 {f_abs} 던지며 발을 빼는데도, 기관들이 {i_abs} 뚝심 있게 순매수하며 주가를 주도하고 있어! 토종 기관의 바닥 지지력이 살아있으니 20일선 지지 여부 꼭 체크하자!"
                else:
                    supply_content = f"⚖️ 수급 눈치싸움 중!\n최근 5일간 외놈({f_abs})과 기관({i_abs})의 힘겨루기가 팽팽하게 이어지고 있어! 개미 수급({ind_abs})이 엇갈리며 박스권 눈치싸움이 치열하니까 기준 가격만 철저히 지키자."
            else:
                supply_content = "📊 거래소 수급 집계 대기\n현재 거래소 수급 데이터를 수집 중이야! 이럴 땐 세력 평단 대신 20일 이동평균선을 생존 지지선으로 잡는 게 안전해."
        else:
            pc_ratio = fetch_us_put_call_ratio(ticker)
            if pc_ratio is not None:
                if pc_ratio <= 0.7:
                    supply_content = f"🛸 월가 큰손 옵션 포지션 포착!\n콜옵션 거래량이 풋옵션을 압도 중이야! (풋/콜 비율 {pc_ratio:.2f}) 큰손들이 위로 쏘는 쪽에 강하게 베팅하고 있으니 탄력 기대해 보자!"
                elif pc_ratio >= 1.1:
                    supply_content = f"🚨 월가 헤지 물량 급증 경보!\n풋옵션 거래량이 콜옵션을 넘어서고 있어! (풋/콜 비율 {pc_ratio:.2f}) 큰손들이 하락 방어벽을 치고 눈치 보는 구간이니 지지선 꼭 체크하자!"
                else:
                    supply_content = f"⚖️ 월가 세력들 눈치싸움 중!\n풋옵션과 콜옵션 거래량이 팽팽하게 맞서고 있어! (풋/콜 비율 {pc_ratio:.2f}) 방향성 탐색 구간이니 지지/저항선 잘 체크하며 대응하자!"
            else:
                supply_content = "📊 월가 옵션 수급 대기 중\n현재 옵션 포지션 데이터를 수집 중이야! 방향성 탐색 구간이니 지지/저항선 잘 체크하며 대응하자."

        # HTML 태그 제거: 프론트엔드 마크다운 파서 오류 원천 차단
        tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #실시간속보"
        news_intro = "궁금해할 거 같아서 오늘 어떤 뉴스가 있나 가져왔어 ㅎ"
        news_transition = "\"이런 뉴스 계속 나오면서 지금 시장이 반응하고 있는 거지\""

        sections = [
            {
                "title": f"{status_emoji} 그래서 오늘은 왜 {title_word}?",
                "content": f"{intro_ment}\n\n현재 주가는 {price_str} 기록 중!\n{news_intro}\n\n{news_lines}\n\n{news_transition}\n\n{tags_str}",
                "tags": [f"#{raw_name}", f"#{change_pct:+.2f}%", "#실시간속보"]
            },
            {
                "title": "큰손들은 담고 있을까, 털고 있을까?",
                "content": supply_content
            },
            {
                "title": "여기 깨지면 도망쳐",
                "content": f"🛡️생존 지지선 {ma20_str} ~ 딱! 기억해놔! 이 가격 깨지면 실망 매물 나올 수 있으니 절대 미련 갖지 말고 비중 줄여!\n🧱악성 매물대 {res_str} ~ 최근 고점 부근에 과거 물려있는 개미들의 본전 대기 악성 매물이 쏟아질 수 있어 ㅠㅠ 조심해!"
            },
            {
                "title": "오늘 밤, 이번주 무슨 일이 있나?",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ]
        return jsonify({"sections": sections})

    except Exception as e:
        print("분석 처리 중 에러 발생:", e)
        return jsonify({"error": "데이터 지연"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
