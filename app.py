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

FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '').strip()

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
            for item in items[:2]:
                title_el = item.find('title')
                if title_el is not None and title_el.text:
                    clean = title_el.text.rsplit(' - ', 1)[0]
                    clean = re.sub(r'<[^>]+>', '', clean).strip()
                    headlines.append(clean)
            return headlines
    except Exception:
        return []

def fetch_krx_supply_demand(code_six):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f'https://finance.naver.com/item/main.naver?code={code_six}'
        }
        url = f"https://finance.naver.com/item/frgn.naver?code={code_six}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
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

def get_live_calendar_data(stock_name, ticker_symbol):
    today = datetime.date.today()
    macro_start = (today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    macro_end = (today + datetime.timedelta(days=3)).strftime('%Y-%m-%d')
    
    earn_start = (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    earn_end = (today + datetime.timedelta(days=30)).strftime('%Y-%m-%d')

    earnings_msg = None
    macro_msg = None

    if FINNHUB_KEY:
        is_us_stock = bool(re.match(r'^[A-Za-z]+$', ticker_symbol))
        
        # 1. 미국 주식 실적 조회
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

                        if act is not None and est is not None:
                            diff = act - est
                            status = "어닝 서프라이즈! 🚀" if diff >= 0 else "예상치 하회(쇼크) ⚠️"
                            earnings_msg = f"📝실적 발표 결과: {stock_name} {status}\n• 실제 EPS: ${act:.2f} (예상치 ${est:.2f} 대비 {diff:+.2f})"
                        elif est is not None:
                            earnings_msg = f"📝실적 발표 대기: {stock_name} ({date_str})\n• 시장 예상 EPS: ${est:.2f} (발표 전후 큰 변동성 주의!)"
            except Exception as e:
                print("미국 실적 조회 에러:", e)
        
        # 2. 한국 주식 밸류체인 체크
        else:
            for theme, chain in THEME_CHAIN.items():
                if stock_name in chain['kr_kids']:
                    for boss in chain['us_boss']:
                        boss_event = check_us_boss_earnings(boss)
                        if boss_event:
                            boss_date = boss_event.get('date', '')
                            earnings_msg = f"📝실적 연동 경고: 글로벌 대장주 {boss} 실적 발표 대기 ({boss_date})!\n• {theme} 밸류체인 연동으로 큰 투심 변화가 예상되니 단단히 대비해!"
                            break
                if earnings_msg: break

        # 3. 미국 주요 거시 경제지표 시간 포함 변환 및 조회
        try:
            macro_url = f"https://finnhub.io/api/v1/calendar/economic?from={macro_start}&to={macro_end}&token={FINNHUB_KEY}"
            req = urllib.request.Request(macro_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                m_data = json.loads(resp.read().decode('utf-8'))
                events = m_data.get('economicCalendar', [])
                us_events = [e for e in events if e.get('country') == 'US' and e.get('estimate') is not None]
                if us_events:
                    ev = us_events[0]
                    ev_name = ev.get('event', '미국 핵심 경제지표')
                    ev_est = ev.get('estimate')
                    ev_act = ev.get('actual')
                    time_str = ev.get('time', '')
                    
                    # [핵심] UTC 시간을 한국 시간(KST)으로 변환하는 로직
                    formatted_time = ""
                    if time_str:
                        try:
                            # Finnhub 제공 시간 예: "2024-09-11 12:30:00" (UTC)
                            utc_time = datetime.datetime.strptime(time_str[:19], '%Y-%m-%d %H:%M:%S')
                            # UTC + 9시간 = 한국 시간(KST)
                            kst_time = utc_time + datetime.timedelta(hours=9)
                            weekdays = ['월', '화', '수', '목', '금', '토', '일']
                            wd = weekdays[kst_time.weekday()]
                            formatted_time = kst_time.strftime(f'%m/%d({wd}) %H:%M')
                        except Exception as parse_e:
                            print("시간 변환 에러:", parse_e)
                            formatted_time = time_str
                    
                    time_display = f" [{formatted_time}]" if formatted_time else ""

                    if ev_act is not None:
                        macro_msg = f"📅미국 경제지표 결과: {ev_name}{time_display}\n• 실제치: {ev_act} | 예상치: {ev_est} (시장 실시간 반영 중)"
                    else:
                        macro_msg = f"📅미국 경제지표 발표 대기: {ev_name}{time_display}\n• 시장 예상치: {ev_est} (발표 시간대 변동성 주의!)"
        except Exception as e:
            print("경제 일정 조회 에러:", e)

    if not macro_msg:
        weekday = datetime.datetime.now().weekday()
        if weekday in [0, 1]: macro_msg = "📅주의 일정: 이번 주 미국 핵심 경제지표 및 주요 CPI 발표 대기 중!"
        elif weekday in [2, 3]: macro_msg = "📅주의 일정: 오늘 밤 미국 경제지표 발표 및 연준 인사 발언 예정!"
        else: macro_msg = "📅주의 일정: 주말 간 글로벌 지정학적 이슈와 월요일 개장 전 미 선물 체크 필수!"

    if not earnings_msg:
        earnings_msg = f"📝실적 체크: {stock_name} 개별 모멘텀 장세 지속 중! 수급 턴어라운드 타점에 집중하자."

    return f"{macro_msg}\n{earnings_msg}"

@app.route('/')
def home():
    return "gaemiGTP 전 종목 검색 & 밸류체인/시간변환 레이더 정상 가동 중!"

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

        is_krw = ('-' not in ticker_symbol and ticker_symbol.endswith(('.KS', '.KQ')))
        
        if is_krw:
            clean_price = round_krw_tick(current_price)
            clean_ma20 = round_krw_tick(ma20)
            price_str = f"₩{clean_price:,}"
            ma20_str = f"₩{clean_ma20:,}"
        else:
            price_str = f"${current_price:,.2f}"
            ma20_str = f"${ma20:,.2f}"

        if change_pct > 0.005:
            status_emoji, title_word, desc_word = '🔥', '올랐어', '상승중이야!!!'
        elif change_pct < -0.005:
            status_emoji, title_word, desc_word = '❄️', '숨고르기일까', '하락중이야 ㅠㅠ'
        else:
            status_emoji, title_word, desc_word = '⚖️', '보합일까', '보합(숨고르기) 중이야. 폭풍 전야의 고요함이 느껴지지 않아?'
            change_pct = 0.0

        news_list = fetch_realtime_news(raw_name)
        main_news = news_list[0] if len(news_list) > 0 else f"{raw_name} 관련 메이저 재료 포착"

        indiv, foreign, inst = (None, None, None)
        if clean_code and len(clean_code) == 6:
            indiv, foreign, inst = fetch_krx_supply_demand(clean_code)

        if foreign is not None and inst is not None and (foreign != 0 or inst != 0):
            f_abs = format_shares(abs(foreign)).replace('+', '')
            i_abs = format_shares(abs(inst)).replace('+', '')
            ind_abs = format_shares(abs(indiv)).replace('+', '')

            if foreign > 0 and inst > 0:
                flow_msg = f"🚀 외놈들이 {f_abs}, 기관 성님들이 {i_abs} 쌍끌이 풀매수 드가자!! 개미들만 {ind_abs} 털리는 중, 지금 안 타면 버스 떠난다 꽉 잡아!"
            elif foreign < 0 and inst < 0:
                flow_msg = f"🚨 삐용삐용! 외놈들이 {f_abs}, 기관 아찌들이 {i_abs} 동반 투매 폭격 중! 개미 혼자 {ind_abs} 받다가 피 흘린다, 일단 튀어 ㅠㅠ"
            elif foreign > 0:
                flow_msg = f"👱‍♂️ 외놈들이 혼자 {f_abs} 쓸어 담으면서 멱살 잡고 캐리 중! 여의도 성님들은 {i_abs} 던지면서 간 보고 있어."
            elif inst > 0:
                flow_msg = f"👔 여의도 기관 성님들이 바닥에서 {i_abs} 묵직하게 줍줍 중! (외놈들은 {f_abs} 패대기 치는 중) 뭔가 냄새가 난다!"
            else:
                flow_msg = f"👀 외놈(-{f_abs})·기관(-{i_abs}) 양매도에 개미 군단이 {ind_abs} 온몸으로 받아내는 중! 세력들 눈치싸움 팽팽하다."
            supply_content = flow_msg
        else:
            supply_content = (
                f"🔥수급 레이더: 메이저 세력들의 차익 실현과 신규 매집이 맞물리는 구간이야!\n"
                f"현재 주요 매물대 부근에서 치열한 손바뀜 공방전 진행 중. 세력들의 의도를 잘 파악해 보자!"
            )

        sections = [
            {
                "title": f"{status_emoji} 그래서 오늘은 왜 {title_word}?",
                "content": f"개미들아! {raw_name} {change_pct:+.2f}% {desc_word}\n현재 실시간 주가는 {price_str} 기록 중!\n\n오늘 터진 핵심 뉴스 헤드라인이야:\n📰 \"{main_news}\"\n이슈가 전해지면서 세력들의 매매가 요동치고 있어. 꽉 잡아!",
                "tags": [f"#{raw_name}", f"#{change_pct:+.2f}%", "#실시간속보"]
            },
            {
                "title": "지금 세력은 사고 있어, 팔고 있어?",
                "content": supply_content
            },
            {
                "title": "여기 깨지면 도망쳐라!",
                "content": f"🛡️생존 지지선: {ma20_str} (딱! 기억해놔!)\n이 가격 깨지면 투매 나오니까 절대 미련 갖지 말고 비중 줄여!\n🧱악성 매물대: 최근 고점 부근에 과거 물려있는 개미들의 본전 대기 물량이 쏟아질 수 있어 ㅠㅠ."
            },
            {
                "title": "🐜 오늘 밤, 내일 무슨 일이 있나?",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ]
        return jsonify({"sections": sections})

    except Exception as e:
        print("분석 처리 중 에러 발생:", e)
        return jsonify({"error": "데이터 지연"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
