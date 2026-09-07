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

# 미국 연준(Fed) 및 노동통계국(BLS) 공식 발표 스케줄 기반 엔진 (429 차단 문제 해결)
def get_official_macro_schedule():
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_tz)
    
    # 공식 발표 확정 캘린더 (한국 시간 KST 기준 변환 완료)
    schedule = [
        {"name": "미국 8월 소비자물가지수(CPI) 발표", "dt": datetime.datetime(2026, 9, 11, 21, 30, tzinfo=kst_tz), "est": "0.2% (전월대비)"},
        {"name": "미국 연준 FOMC 기준금리 결정", "dt": datetime.datetime(2026, 9, 17, 3, 0, tzinfo=kst_tz), "est": "기준금리 3.50%~3.75%"},
        {"name": "미국 생산자물가지수(PPI) 발표", "dt": datetime.datetime(2026, 9, 18, 21, 30, tzinfo=kst_tz), "est": "0.2% (전월대비)"},
        {"name": "미국 개인소비지출(PCE) 물가지수", "dt": datetime.datetime(2026, 9, 25, 21, 30, tzinfo=kst_tz), "est": "2.6% (전년대비)"},
        {"name": "미국 9월 비농업 고용보고서(NFP)", "dt": datetime.datetime(2026, 10, 2, 21, 30, tzinfo=kst_tz), "est": "15만 건 (예상)"},
        {"name": "미국 9월 소비자물가지수(CPI) 발표", "dt": datetime.datetime(2026, 10, 14, 21, 30, tzinfo=kst_tz), "est": "시장 전망치 대기"},
        {"name": "미국 연준 FOMC 기준금리 결정", "dt": datetime.datetime(2026, 10, 29, 3, 0, tzinfo=kst_tz), "est": "금리 추가 인하 여부 촉각"},
        {"name": "미국 10월 소비자물가지수(CPI) 발표", "dt": datetime.datetime(2026, 11, 10, 22, 30, tzinfo=kst_tz), "est": "시장 전망치 대기"},
        {"name": "미국 11월 소비자물가지수(CPI) 발표", "dt": datetime.datetime(2026, 12, 10, 22, 30, tzinfo=kst_tz), "est": "시장 전망치 대기"},
        {"name": "미국 연준 FOMC 기준금리 결정", "dt": datetime.datetime(2026, 12, 10, 4, 0, tzinfo=kst_tz), "est": "연말 금리 향방 결정"}
    ]

    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    for ev in schedule:
        if ev['dt'] >= now_kst:
            dt = ev['dt']
            wd = weekdays[dt.weekday()]
            time_str = dt.strftime(f"%m/%d({wd}) %H:%M")
            return f"📅미국 경제지표 발표 대기: {ev['name']} [{time_str}]\n• 시장 예상치: {ev['est']} (한국 시간 발표 직후 선물 체크!)"

    return "📅주의 일정: 주요국 통화정책 및 글로벌 매크로 지표 변동성 주의!"

def get_live_calendar_data(stock_name, ticker_symbol):
    today = datetime.date.today()
    earn_start = (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    earn_end = (today + datetime.timedelta(days=30)).strftime('%Y-%m-%d')

    earnings_msg = None

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

                        if act is not None and est is not None:
                            diff = act - est
                            status = "어닝 서프라이즈! 🚀" if diff >= 0 else "예상치 하회(쇼크) ⚠️"
                            earnings_msg = f"📝실적 발표 결과: {stock_name} {status}\n• 실제 EPS: ${act:.2f} (예상치 ${est:.2f} 대비 {diff:+.2f})"
                        elif est is not None:
                            earnings_msg = f"📝실적 발표 대기: {stock_name} ({date_str})\n• 시장 예상 EPS: ${est:.2f} (발표 전후 큰 변동성 주의!)"
            except Exception as e:
                print("미국 실적 조회 에러:", e)
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

    macro_msg = get_official_macro_schedule()

    if not earnings_msg:
        earnings_msg = f"📝실적 체크: {stock_name} 개별 모멘텀 장세 지속 중! 수급 턴어라운드 타점에 집중하자."

    return f"{macro_msg}\n{earnings_msg}"

@app.route('/')
def home():
    return "gaemiGTP 초고속 공식 매크로 캘린더 엔진 가동 중!"

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

        supply_content = (
            "⚙️ 실시간 프로그램 수급 엔진 연동 준비 중!\n"
            "증권사 API 다이렉트 연결을 통해 더욱 정교한 틱 단위 세력 매수/매도 데이터를 제공할 예정입니다.\n"
            "시스템 업데이트 전까지는 차트 지지선과 밸류체인 모멘텀에 집중해 주세요!"
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
