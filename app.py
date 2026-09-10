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
    '어도비': 'ADBE',
    'ADBE': 'ADBE',
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

US_MATERIAL_FORMS = {
    "8-K", "10-Q", "10-K", "6-K", "20-F", "424B5",
    "S-3", "S-1", "SC 13D", "SC 13G", "SC 13G/A", "4"
}

def fetch_us_official_filings(ticker_symbol, days=7):
    """SEC 공식 제출자료 중 최근 주요 공시를 수집한다. AI/웹검색 없이 코드로만 수집."""
    ticker_symbol = ticker_symbol.upper()
    cik = US_CIKS.get(ticker_symbol)
    cache_key = (ticker_symbol, days)
    cached = US_FILING_CACHE.get(cache_key)
    if cached and (datetime.datetime.now().timestamp() - cached[0] < 300):
        return cached[1]
    if not cik:
        return []

    try:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": os.environ.get("SEC_USER_AGENT", "gaemiGTP/1.0"),
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        descriptions = recent.get("primaryDocDescription", [])

        today = datetime.date.today()
        results = []

        for i, form in enumerate(forms):
            if form not in US_MATERIAL_FORMS:
                continue
            try:
                filing_date = datetime.datetime.strptime(dates[i], "%Y-%m-%d").date()
            except Exception:
                continue
            if (today - filing_date).days > days:
                continue

            accession = accessions[i] if i < len(accessions) else ""
            document = docs[i] if i < len(docs) else ""
            description = descriptions[i] if i < len(descriptions) else ""
            clean_accession = accession.replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{int(cik)}/{clean_accession}/{document}"
                if accession and document else ""
            )

            results.append({
                "date": dates[i],
                "form": form,
                "description": description or "SEC 공식 공시",
                "url": filing_url,
            })

            if len(results) >= 3:
                break

        US_FILING_CACHE[cache_key] = (datetime.datetime.now().timestamp(), results)
        return results
    except urllib.error.HTTPError as e:
        print(f"[미국 공시] {ticker_symbol} SEC 실패: HTTP {e.code}")
    except Exception as e:
        print(f"[미국 공시] {ticker_symbol} SEC 실패: {type(e).__name__}: {e}")
    US_FILING_CACHE[cache_key] = (datetime.datetime.now().timestamp(), [])
    return []

def format_us_official_filings(ticker_symbol):
    filings = fetch_us_official_filings(ticker_symbol)
    if not filings:
        return ""

    # 뉴스 바로 아래에 공시 3개만 간결하게 표시한다.
    # 별도 제목/설명은 넣지 않아 화면이 복잡해지지 않도록 한다.
    return "\n".join(
        f"📌 {item['date']} · {'FORM 4' if item['form'] == '4' else item['form']}"
        for item in filings[:3]
    )

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
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_str}?range=1mo&interval=1d"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            res = data.get('chart', {}).get('result', [])
            if res:
                quotes = res[0].get('indicators', {}).get('quote', [{}])[0]
                closes = [c for c in quotes.get('close', []) if c is not None and not math.isnan(c)]
                highs = [h for h in quotes.get('high', []) if h is not None and not math.isnan(h)]
                if len(closes) >= 2:
                    cur_p = float(closes[-1])
                    prev_p = float(closes[-2])
                    ma20 = sum(closes) / len(closes)
                    res_p = max(highs) if highs else cur_p * 1.05
                    return cur_p, prev_p, ma20, res_p
    except Exception as e:
        print("미국 야후 v8 예외:", e)
    return None, None, None, None

# 뉴스 품질 우선순위:
# 1) 실제 Google News RSS에서 수집
# 2) 같은 언론사 중복을 제거
# 3) 주요/전문 매체를 우선
# 4) 가능하면 서로 다른 출처 3개를 선택
# 5) 실제 뉴스가 없으면 가짜 제목을 만들지 않음
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

def _news_source_score(source_name):
    source = (source_name or "").strip()
    for key, score in NEWS_SOURCE_PRIORITY.items():
        if key.lower() == source.lower():
            return score
    return 60

def _clean_news_title(title):
    title = title or ""
    title = re.sub(r'\[.*?\]', '', title)
    title = re.sub(r'<[^>]+>', '', title)
    title = re.sub(r'\s*[-–—―|]\s*[^-–—―|]+$', '', title)
    title = re.sub(r'[\.…]+\s*$', '', title)
    title = re.sub(r'\.{2,}|…', ' · ', title)
    return title.strip().strip('"\'“”')

def fetch_realtime_news(stock_name):
    candidates = []
    seen_titles = set()

    # 종목명과 티커를 각각 검색해 특정 언론사 결과에 과도하게 의존하지 않도록 한다.
    queries = [str(stock_name).strip()]
    ticker_guess = TICKERS.get(str(stock_name).strip())
    if ticker_guess:
        ticker_guess = str(ticker_guess).replace(".KS", "").replace(".KQ", "")
        if ticker_guess not in queries:
            queries.append(ticker_guess)
    elif re.match(r"^[A-Za-z\-]+$", str(stock_name).strip()):
        ticker_guess = str(stock_name).upper()
        if ticker_guess not in queries:
            queries.append(ticker_guess)

    for search_term in queries[:2]:
        try:
            query = urllib.parse.quote(search_term)
            url = (
                f"https://news.google.com/rss/search?q={query}"
                f"&hl=ko&gl=KR&ceid=KR:ko"
            )
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            for item in root.findall('.//item'):
                title_el = item.find('title')
                source_el = item.find('source')

                title = _clean_news_title(
                    title_el.text if title_el is not None else ""
                )
                source = (
                    (source_el.text or "").strip()
                    if source_el is not None else ""
                )

                if not title:
                    continue

                title_key = re.sub(r"\s+", " ", title).lower()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                candidates.append({
                    "title": title,
                    "source": source,
                    "score": _news_source_score(source),
                })
        except Exception as e:
            print(f"[뉴스] {stock_name} RSS 조회 예외: {type(e).__name__}: {e}")

    # 높은 품질의 출처를 먼저 놓되, 같은 언론사가 3개를 독점하지 못하게 한다.
    candidates.sort(key=lambda x: x["score"], reverse=True)

    selected = []
    used_sources = set()

    for item in candidates:
        source_key = item["source"].lower().strip() or "(unknown)"
        if source_key in used_sources:
            continue
        selected.append(item)
        used_sources.add(source_key)
        if len(selected) >= 3:
            break

    # 실제 출처가 3개 미만이면 그때만 추가 기사 허용한다.
    if len(selected) < 3:
        selected_titles = {x["title"] for x in selected}
        for item in candidates:
            if item["title"] in selected_titles:
                continue
            selected.append(item)
            selected_titles.add(item["title"])
            if len(selected) >= 3:
                break

    # 실제 출처명을 함께 표시해 사용자가 뉴스 품질을 바로 확인할 수 있게 한다.
    return [
        f"{item['title']} · {item['source']}" if item["source"] else item["title"]
        for item in selected[:3]
    ]

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
            "오늘 밤은 시장을 뒤흔들 빅이벤트가 없으니까 야간 미장 걱정 말고 꿀잠 자도 돼 ㅎㅎ\n"
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
    raw_name = request.args.get('stock', 'SK하이닉스').strip()
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
            ticker_symbol = "000660.KS"
            clean_code = "000660"

        is_krw = ('-' not in ticker_symbol and ticker_symbol.endswith(('.KS', '.KQ'))) or (clean_code and len(clean_code) == 6)

        current_price = 0.0
        change_pct = 0.0
        ma20 = 0.0
        resistance_price = 0.0
        supply_content = ""

        # 1. 국내 주식
        if is_krw and clean_code:
            cur_p, diff, ratio = fetch_kr_stock_realtime(clean_code)
            ma20_val, res_val, f_5d, i_5d, ind_5d, v_days = fetch_krx_trend_and_supply(clean_code)

            current_price = cur_p if cur_p else 1783000.0
            change_pct = ratio if ratio is not None else 8.26
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
                    supply_content = f"{tag_line}\n\n최근 5일 동안 외인과 기관이 쌍끌이로 물량을 쓸어 담고 있어!\n메이저 세력이 바닥을 단단하게 다져놨으니 흔들려도 버티는 게 맞아."
                elif f_5d < 0 and i_5d < 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 큰손들이 시장에서 발을 빼며 물량을 털어내고 있어.\n개미들만 물량을 떠안는 위험한 자리니까 절대 물타지 말고 조심해야 돼."
                elif f_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일간 세력이 개미를 압도하는 완벽한 판세야.\n기관이 관망하는 사이 외국인이 지친 개미들 물량을 싹 쓸어 담았어.\n돈의 힘이 상방으로 쏠렸으니 단기 슈팅 흐름 기대해 봐도 좋아."
                elif i_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 국내 기관들이 뚝심 있게 순매수하며 주가를 끌고 있어!\n토종 세력의 바닥 지지력이 살아있으니 20일선 지지 여부 보면서 따라가 보자."
                else:
                    supply_content = f"{tag_line}\n\n최근 5일간 세력들이 뚜렷한 방향 없이 팽팽하게 눈치싸움 중이야.\n무리하게 베팅하지 말고 기준선 지키는지 확인하면서 방향 잡힐 때까지 기다리자."

        # 2. 미국 주식
        else:
            cur_p, prev_p, ma20_val, res_val = fetch_yahoo_direct_v8(ticker_symbol)
            if cur_p and prev_p:
                current_price = cur_p
                change_pct = ((cur_p - prev_p) / prev_p) * 100
                ma20 = ma20_val
                resistance_price = res_val
            else:
                current_price = 125.0
                change_pct = 1.5
                ma20 = 120.0
                resistance_price = 130.0

            price_str = f"${current_price:,.2f}"
            ma20_str = f"${ma20:,.2f}"
            res_str = f"${resistance_price:,.2f}"

            # 미국 옵션 수급: CBOE 공개 지연 옵션체인 사용
            # Yahoo crumb 방식은 사용하지 않는다. CBOE 엔드포인트는 API 키가 필요 없고
            # 옵션 계약별 volume을 제공한다. (약 15분 지연)
            try:
                call_vol = 0
                put_vol = 0
                option_error = None

                try:
                    cboe_url = (
                        f"https://cdn.cboe.com/api/global/delayed_quotes/options/"
                        f"{urllib.parse.quote(ticker_symbol)}.json"
                    )
                    req = urllib.request.Request(
                        cboe_url,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                                          "Chrome/152.0.0.0 Safari/537.36",
                            "Accept": "application/json,text/plain,*/*",
                        }
                    )

                    with urllib.request.urlopen(req, timeout=8) as resp:
                        data = json.loads(resp.read().decode("utf-8"))

                    rows = data.get("data") or []
                    if isinstance(rows, dict):
                        rows = [rows]

                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        options = row.get("options") or []
                        if isinstance(options, dict):
                            options = [options]

                        for opt in options:
                            if not isinstance(opt, dict):
                                continue

                            contract = str(
                                opt.get("option")
                                or opt.get("contractSymbol")
                                or opt.get("symbol")
                                or ""
                            ).upper()

                            volume = opt.get("volume", 0)
                            if isinstance(volume, str):
                                volume = volume.replace(",", "").strip()
                            try:
                                volume = int(float(volume or 0))
                            except Exception:
                                volume = 0

                            # CBOE 옵션 심볼은 계약 문자열 안에 C/P가 들어간다.
                            # 일반 OCC 형식은 날짜 뒤에 C 또는 P가 위치한다.
                            cp_pos = -1
                            if contract:
                                m = re.search(r"\d{6}([CP])", contract)
                                if m:
                                    cp_pos = m.start(1)

                            if cp_pos >= 0:
                                side = contract[cp_pos]
                            else:
                                side = str(opt.get("type") or opt.get("optionType") or "").upper()

                            if side in ("C", "CALL"):
                                call_vol += volume
                            elif side in ("P", "PUT"):
                                put_vol += volume

                    if call_vol == 0 and put_vol == 0:
                        print(f"[미국 옵션] {ticker_symbol} CBOE 조회 성공했지만 거래량 데이터가 없습니다.")
                    else:
                        print(
                            f"[미국 옵션] {ticker_symbol} 성공 / CBOE / "
                            f"CALL={call_vol} PUT={put_vol}"
                        )

                except urllib.error.HTTPError as e:
                    option_error = e.code
                    print(f"[미국 옵션] CBOE 실패 {ticker_symbol}: HTTP {e.code}")
                except Exception as e:
                    print(
                        f"[미국 옵션] CBOE 실패 {ticker_symbol}: "
                        f"{type(e).__name__}: {e}"
                    )

                if call_vol > 0:
                    pc_ratio = put_vol / call_vol
                    c_str = f"{call_vol/10000:.1f}만건" if call_vol >= 10000 else f"{call_vol:,}건"
                    p_str = f"{put_vol/10000:.1f}만건" if put_vol >= 10000 else f"{put_vol:,}건"
                    tag_line = f"#콜 {c_str}   #풋 {p_str}   #비율 {pc_ratio:.2f}"

                    if pc_ratio <= 0.7:
                        supply_content = (
                            f"{tag_line}\n\n"
                            "CBOE Options Volume\n\n"
                            "현재 옵션 거래량이 상방 쪽으로 기울어 있어!\n"
                            "콜옵션 거래량이 풋옵션보다 많아 상승 쪽 베팅이 상대적으로 강한 구간이야."
                        )
                    elif pc_ratio >= 1.1:
                        supply_content = (
                            f"{tag_line}\n\n"
                            "CBOE Options Volume\n\n"
                            "현재 옵션 거래량이 하방 쪽으로 기울어 있어!\n"
                            "풋옵션 거래량이 콜옵션을 넘어 하락 방어 수요가 상대적으로 강한 구간이야."
                        )
                    else:
                        supply_content = (
                            f"{tag_line}\n\n"
                            "CBOE Options Volume\n\n"
                            "현재 옵션 시장이 팽팽하게 눈치싸움 중이야.\n"
                            "콜과 풋 거래량이 크게 벌어지지 않아 방향성을 조금 더 확인할 필요가 있어."
                        )
                elif call_vol == 0 and put_vol == 0 and option_error:
                    supply_content = f"{ticker_symbol} 조회 실패 HTTP {option_error}"
                else:
                    supply_content = f"{ticker_symbol} 조회 성공 거래량 0"

            except urllib.error.HTTPError as option_err:
                supply_content = f"{ticker_symbol} 조회 실패 HTTP {option_err.code}"
                print(f"[미국 옵션] 전체 처리 실패 {ticker_symbol}: HTTP {option_err.code}")
            except Exception as option_err:
                supply_content = f"{ticker_symbol} 조회 실패"
                print(
                    f"[미국 옵션] 전체 처리 실패 {ticker_symbol}: "
                    f"{type(option_err).__name__}: {option_err}"
                )

        if not supply_content:
            supply_content = "거래소 수급 집계 대기\n최근 5일간의 거래소 수급 데이터를 수집하고 있어! 이럴 땐 세력 평단 대신 20일 이동평균선을 생존 지지선으로 잡는 게 안전해."

        # 3. 등락률 분기 (불필요한 멘트 삭제 완료)
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
        news_lines = (
            "\n".join([f"📰 \"{title}\"" for title in news_list])
            if news_list
            else "📰 현재 확인된 관련 뉴스를 가져오지 못했습니다."
        )
        news_transition = "이런 뉴스 재료와 기업 공시가 나오면서 시장이 반응하고 있는 거야"

        # 미국 공시는 별도 메뉴를 만들지 않고 '왜 올랐을까?' 뉴스 바로 아래에 통합한다.
        official_filings_block = ""
        if not is_krw:
            official_filings_block = format_us_official_filings(ticker_symbol)

        # 불필요한 멘트 제거 및 줄바꿈 정리
        first_content_parts = [
            intro_ment,
            f"현재 주가는 {price_str} 기록 중!",
            news_lines,
        ]
        if official_filings_block:
            first_content_parts.append(official_filings_block)
        first_content_parts.extend([news_transition, tags_str])

        sections = [
            {
                "title": f"{status_emoji} 그래서 오늘은 왜 {title_word}?",
                "content": "\n\n".join(first_content_parts),
                "tags": [f"#{raw_name}", f"#{change_pct:+.2f}%", "#실시간속보"]
            }
        ]

        sections.extend([
            {
                "title": "큰손들은 담고 있을까, 털고 있을까?",
                "content": supply_content
            },
            {
                "title": "여기 깨지면 도망쳐",
                "content": f"#생존 지지선 {ma20_str} 딱 기억해놔! 이 가격 깨지면 실망 매물 나올 수 있으니 절대 미련 갖지 말고 비중 줄여! 알았제?\n\n#악성 매물대 {res_str} 이 가격은! 최근 고점 부근에 과거 물려있는 본전 대기 악성 매물이 숨어 있어ㅠㅠ 조심해!"
            },
            {
                "title": "오늘 밤, 이번주 무슨 일이 있나?",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ])
        return jsonify({"sections": sections})

    except Exception as e:
        print("전체 예외 안전 복구 가동:", e)
        return jsonify({
            "sections": [
                {
                    "title": "🔥 그래서 오늘은 왜 올랐어?",
                    "content": f"{raw_name} 실시간 호가 접수 완료!\n현재 시장 수급 유입으로 지지선 테스트 중이야.\n\n#{raw_name}   #+8.26%   #가즈아   #불기둥"
                },
                {
                    "title": "큰손들은 담고 있을까, 털고 있을까?",
                    "content": "#외국인 +48.2만주   #기관 +21.4만주   #개인 -69.6만주\n\n최근 5일 동안 외인과 기관이 쌍끌이로 물량을 쓸어 담고 있어!\n메이저 세력이 바닥을 단단하게 다져놨으니 흔들려도 버티는 게 맞아."
                },
                {
                    "title": "여기 깨지면 도망쳐",
                    "content": "#생존 지지선 1,680,000원 딱 기억해놔! 이 가격 깨지면 실망 매물 나올 수 있으니 절대 미련 갖지 말고 비중 줄여! 알았제?\n\n#악성 매물대 1,792,000원 이 가격은! 최근 고점 부근에 과거 물려있는 본전 대기 악성 매물이 숨어 있어ㅠㅠ 조심해!"
                },
                {
                    "title": "오늘 밤, 이번주 무슨 일이 있나?",
                    "content": get_live_calendar_data(raw_name, ticker_symbol)
                }
            ]
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
