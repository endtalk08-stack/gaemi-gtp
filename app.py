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
    'ORCL': '오라클',
    'NVDA': '엔비디아',
    'MSFT': '마이크로소프트',
    'TSLA': '테슬라',
    'AAPL': '애플',
    'GOOGL': '구글',
    'AMZN': '아마존',
    'META': '메타',
    'LLY': '일라이릴리',
    'NVO': '노보노디스크'
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
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')
            headlines = []
            junk_keywords = ['자막뉴스', '현장영상', '영상뉴스', '다시보기', '풀영상', '포토', '카드뉴스']

            for item in items:
                title_el = item.find('title')
                if title_el is not None and title_el.text:
                    title = title_el.text

                    if any(junk in title for junk in junk_keywords):
                        continue

                    title = re.sub(r'\s*[-–—|]\s*[^-–—|]+$', '', title)
                    title = re.sub(r'\[.*?\]', '', title)
                    title = re.sub(r'\(.*?\)', '', title)
                    title = re.sub(r'<[^>]+>', '', title)
                    clean = title.strip().strip('"\'“”')

                    if len(clean) >= 10:
                        headlines.append(clean)
                    
                    if len(headlines) == 2:
                        break

            return headlines
    except Exception:
        return []

def fetch_krx_5d_supply_demand(code_six):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Referer': f'https://finance.naver.com/item/main.naver?code={code_six}'
        }
        url = f"https://finance.naver.com/item/frgn.naver?code={code_six}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
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
        print("5일 수급 집계 에러:", e)
    return None, None, None, 0

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

def get_official_macro_schedule():
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_tz)
    
    schedule = [
        {"name": "미국 8월 소비자물가지수 CPI", "dt": datetime.datetime(2026, 9, 11, 21, 30, tzinfo=kst_tz), "est": "0.2%"},
        {"name": "미국 연준 FOMC 기준금리 결정", "dt": datetime.datetime(2026, 9, 17, 3, 0, tzinfo=kst_tz), "est": "기준금리 3.50%에서 3.75%"},
        {"name": "미국 생산자물가지수 PPI", "dt": datetime.datetime(2026, 9, 18, 21, 30, tzinfo=kst_tz), "est": "0.2%"},
        {"name": "미국 개인소비지출 PCE 물가지수", "dt": datetime.datetime(2026, 9, 25, 21, 30, tzinfo=kst_tz), "est": "2.6%"},
        {"name": "미국 9월 비농업 고용보고서 NFP", "dt": datetime.datetime(2026, 10, 2, 21, 30, tzinfo=kst_tz), "est": "15만 건"},
        {"name": "미국 9월 소비자물가지수 CPI", "dt": datetime.datetime(2026, 10, 14, 21, 30, tzinfo=kst_tz), "est": "시장 전망치 대기"},
        {"name": "미국 연준 FOMC 기준금리 결정", "dt": datetime.datetime(2026, 10, 29, 3, 0, tzinfo=kst_tz), "est": "금리 추가 인하 여부 촉각"}
    ]

    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    for ev in schedule:
        if ev['dt'] >= now_kst:
            dt = ev['dt']
            wd = weekdays[dt.weekday()]
            time_str = f"{dt.month}월 {dt.day}일 {wd}요일"
            return f"일정 체크해 보면, 다가오는 {time_str}에 {ev['name']} 발표가 예정되어 있어. 시장 예상치는 {ev['est']} 수준인데 발표 직후 야간 선물이 크게 출렁일 수 있으니 꼭 주의하자."

    return "글로벌 매크로 지표 일정이 촘촘하게 잡혀 있는 구간이야. 지수 변동성에 유의하면서 지지선 잘 지키자."

def get_live_calendar_data(stock_name, ticker_symbol):
    today = datetime.date.today()
    earn_start = (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    earn_end = (today + datetime.timedelta(days=30)).strftime('%Y-%m-%d')

    earnings_msg = ""

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
                            status = "어닝 서프라이즈를 기록했어" if diff >= 0 else "예상치를 밑돌며 실적 쇼크가 나왔어"
                            earnings_msg = f"실적 소식으로는 방금 {kr_label} 실적이 발표됐는데 {status}. 실제 주당순이익이 {act:.2f}달러로 집계되었으니 참고해."
                        elif est is not None:
                            try:
                                e_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                                date_str = f"{e_date.month}월 {e_date.day}일"
                            except:
                                pass
                            earnings_msg = f"실적 일정도 중요해. {date_str}에 {kr_label} 실적 발표가 잡혀 있거든. 발표 전후로 주가 변동 폭이 커질 수 있으니 조심하자."
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
                            try:
                                b_date = datetime.datetime.strptime(boss_date, '%Y-%m-%d')
                                boss_date = f"{b_date.month}월 {b_date.day}일"
                            except:
                                pass

                            earnings_msg = f"그리고 우리 {theme} 대장주인 미국 {kr_boss_name} 실적이 {boss_date}에 나와. 대장주 실적에 따라 국내 관련주도 같이 출렁일 테니 미리 대비해 두자."
                            break
                if earnings_msg: break

    macro_msg = get_official_macro_schedule()

    if earnings_msg:
        return f"{macro_msg}\n\n{earnings_msg}"
    else:
        return f"{macro_msg}\n\n지금은 개별 종목 수급 장세인 만큼 세력 평단가와 수급 턴어라운드 타이밍에 집중하자."

@app.route('/')
def home():
    return "gaemiGTP 대화형 수급 분석 엔진 정상 가동 중"

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
            price_str = f"{clean_price:,}원"
            ma20_str = f"{clean_ma20:,}원"
        else:
            price_str = f"{current_price:,.2f}달러"
            ma20_str = f"{ma20:,.2f}달러"

        if change_pct > 0.005:
            title_word, desc_word = '올랐어?', '상승 흐름을 타고 있어.'
        elif change_pct < -0.005:
            title_word, desc_word = '내렸어?', '조정 국면에 들어가 있어.'
        else:
            title_word, desc_word = '보합이야?', '방향성을 탐색하며 숨고르기 중이야.'
            change_pct = 0.0

        # 뉴스: 기호 없이 자연스러운 문맥 연결
        news_list = fetch_realtime_news(raw_name)
        if news_list:
            if len(news_list) > 1:
                news_lines = f"오늘 장중에 보니까 {news_list[0]} 소식이랑 {news_list[1]} 소식이 전해지면서 시장 관심이 집중됐어."
            else:
                news_lines = f"오늘 장중에 보니까 {news_list[0]} 소식이 전해지면서 시장이 반응하고 있어."
        else:
            news_lines = "현재 두드러진 단독 이슈보다는 세력들 수급 공방으로 주가가 움직이는 국면이야."

        indiv_5d, foreign_5d, inst_5d, days = (None, None, None, 0)
        if clean_code and len(clean_code) == 6:
            indiv_5d, foreign_5d, inst_5d, days = fetch_krx_5d_supply_demand(clean_code)

        if foreign_5d is not None and inst_5d is not None and days > 0:
            f_abs = format_shares(foreign_5d)
            i_abs = format_shares(inst_5d)
            ind_abs = format_shares(indiv_5d)

            if foreign_5d > 0 and inst_5d > 0:
                supply_content = f"외국인이 최근 {days}일간 무려 {f_abs}를 담아내며 바닥을 탄탄하게 다지고 있어. 기관도 {i_abs} 거들면서 쌍끌이 매집 패턴이 뚜렷해. 단기 흔들기가 나오더라도 세력 평단가 위라면 차분하게 버텨보자."
            elif foreign_5d < 0 and inst_5d < 0:
                supply_content = f"경계해야 할 타이밍이야. 최근 {days}일간 외국인 {f_abs} 물량과 기관 {i_abs} 물량이 동시에 쏟아지고 있어. 개인 수급 {ind_abs}만 온몸으로 물량을 받는 형국이니까 절대 섣불리 물타지 말고 관망하자."
            elif foreign_5d > 0:
                supply_content = f"외국인이 최근 {days}일간 무려 {f_abs}를 순매수하며 버팀목 역할을 해주고 있어. 기관이 {i_abs} 던지면서 간을 보고 있지만 외인 매수세가 받쳐주니 하방 경직성은 탄탄한 편이야."
            elif inst_5d > 0:
                supply_content = f"국내 기관이 최근 {days}일간 무려 {i_abs}를 연속 매집 중이야. 외국인이 {f_abs} 매도세를 보여도 기관이 가격을 방어해 주고 있으니 긍정적인 신호야."
            else:
                supply_content = f"최근 {days}일간 외국인 {f_abs} 물량과 기관 {i_abs} 물량이 엇갈리며 팽팽한 눈치싸움이 이어지고 있어. 개인 수급도 갈리고 있으니 지지 라인을 최우선 기준으로 삼자."
        else:
            supply_content = "현재 거래소 수급 데이터를 집계 중이거나 해외 종목이야. 20일 이동평균선 지지 라인을 방어선으로 보고 접근하는 게 안전해."

        sections = [
            {
                "title": f"그래서 오늘은 왜 {title_word}",
                "content": f"개미들아, {raw_name} 현재 주가는 {price_str} 기록 중이고 {change_pct:+.2f}% {desc_word}\n\n{news_lines}\n\n이슈가 이어지면서 수급이 흔들릴 수 있으니 포지션 관리 잘해두자.",
                "tags": [f"#{raw_name}", f"#{change_pct:+.2f}%", "#실시간속보"]
            },
            {
                "title": "지금 세력은 사고 있어, 팔고 있어?",
                "content": supply_content
            },
            {
                "title": "여기 깨지면 도망쳐라!",
                "content": f"차트 흐름을 보면 20일선 기준 가격이 딱 {ma20_str}이야. 이거 꼭 기억해 둬. 이 가격이 무너지면 직전 고점에 물려있던 대기 매물이 한 번에 쏟아질 수 있으니까 미련 갖지 말고 비중부터 덜어내야 해."
            },
            {
                "title": "오늘 밤, 내일 무슨 일이 있나?",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ]
        return jsonify({"sections": sections})

    except Exception as e:
        print("분석 처리 중 에러 발생:", e)
        return jsonify({"error": "데이터 지연"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
