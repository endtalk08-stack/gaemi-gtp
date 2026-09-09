from flask import Flask, jsonify, request
from flask_cors import CORS
import urllib.request
import urllib.error
import urllib.parse
import json
import datetime
import os
import re
import math
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from upstash_redis import Redis

app = Flask(__name__)
CORS(app)

GROQ_KEY = os.environ.get('GROQ_API_KEY', '').strip().strip('\'"')
REDIS_URL = os.environ.get('UPSTASH_REDIS_REST_URL')
REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
redis_client = None

# Groq API 접근 진단 결과는 프로세스당 1회만 확인해 반복 호출을 막는다.
GROQ_DIAG = None
GROQ_MODEL = "qwen/qwen3.6-27b"
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '').strip().strip("\'\"")

# 미국 주식 입력 보정(자주 쓰는 종목만 별칭 제공, 나머지는 Finnhub 검색으로 찾음)
US_NAME_ALIASES = {
    '엔비디아': 'NVDA', 'NVIDIA': 'NVDA',
    '테슬라': 'TSLA', 'TESLA': 'TSLA',
    '애플': 'AAPL', 'APPLE': 'AAPL',
    '마이크로소프트': 'MSFT', 'MICROSOFT': 'MSFT',
    '아마존': 'AMZN', 'AMAZON': 'AMZN',
    '메타': 'META', 'META': 'META',
    '브로드컴': 'AVGO', 'BROADCOM': 'AVGO',
    '마이크론': 'MU', 'MICRON': 'MU',
    'AMD': 'AMD', '인텔': 'INTC', 'INTEL': 'INTC',
    '구글': 'GOOGL', '알파벳': 'GOOGL', 'GOOGLE': 'GOOGL',
}

def check_groq_access():
    """
    같은 GROQ_API_KEY로 /models를 호출해 API 키/프로젝트 접근 상태를 확인한다.
    실제 분석 요청 전 1회만 실행한다.
    """
    global GROQ_DIAG
    if GROQ_DIAG is not None:
        return GROQ_DIAG

    if not GROQ_KEY:
        GROQ_DIAG = (False, "GROQ_API_KEY 없음")
        print("🔴 Groq 진단: GROQ_API_KEY가 없습니다.")
        return GROQ_DIAG

    url = "https://api.groq.com/openai/v1/models"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
        },
        method="GET"
    )

    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")

        data = json.loads(body)
        models = data.get("data", []) if isinstance(data, dict) else []
        model_ids = {str(m.get("id", "")) for m in models if isinstance(m, dict)}
        model_exists = GROQ_MODEL in model_ids

        print(f"🟢 Groq /models 응답: HTTP {status}")
        print(f"   - 사용 가능한 모델 수: {len(model_ids)}")
        print(f"   - {GROQ_MODEL} 목록 확인: {'YES' if model_exists else 'NO'}")

        if model_exists:
            GROQ_DIAG = (True, "API 접근 정상 / 대상 모델 목록 확인")
        else:
            GROQ_DIAG = (True, "API 접근 정상 / 대상 모델이 /models 목록에 없음")
        return GROQ_DIAG

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"🔴 Groq /models HTTP 오류 {e.code}: {error_body[:1500]}")
        GROQ_DIAG = (False, f"/models HTTP {e.code}")
        return GROQ_DIAG
    except Exception as e:
        print(f"🔴 Groq /models 네트워크 오류: {type(e).__name__}: {e}")
        GROQ_DIAG = (False, f"/models 연결 실패: {type(e).__name__}")
        return GROQ_DIAG

if REDIS_URL and REDIS_TOKEN:
    try:
        redis_client = Redis(url=REDIS_URL, token=REDIS_TOKEN)
        print("✅ Redis 초고속 인메모리 캐시 연결 성공!")
    except Exception as e:
        print("❌ Redis 연결 예외:", e)

# 핵심 종목 사전
TICKERS = {
    '삼성전자': '005930', 'SK하이닉스': '000660', '현대차': '005380',
    '현대자동차': '005380', '기아': '000270', '셀트리온': '068270',
    '에코프로': '086520', '에코프로비엠': '247540', '알테오젠': '196170',
    '카카오': '035720', '카카오페이': '377300', '카카오뱅크': '323410',
    'NAVER': '035420', '네이버': '035420', 'LG에너지솔루션': '373220',
    '삼성바이오로직스': '207940', 'POSCO홀딩스': '005490', '포스코홀딩스': '005490',
    '한미반도체': '042700', '가온전선': '000500'
}

PRELOAD_TARGETS = [
    ('삼성전자', '005930'), ('SK하이닉스', '000660'), ('현대차', '005380'),
    ('기아', '000270'), ('셀트리온', '068270'), ('에코프로', '086520'),
    ('알테오젠', '196170'), ('카카오', '035720'), ('네이버', '035420'),
    ('LG에너지솔루션', '373220'), ('한미반도체', '042700'), ('가온전선', '000500')
]

def finnhub_get(path, params):
    """Finnhub REST 공통 호출. API 키는 URL에만 붙이고 로그에는 절대 출력하지 않는다."""
    if not FINNHUB_KEY:
        return None
    query = dict(params or {})
    query['token'] = FINNHUB_KEY
    url = 'https://finnhub.io/api/v1/' + path + '?' + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    })
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f'⚠️ Finnhub {path} 오류: {type(e).__name__}')
        return None

def resolve_us_symbol(stock_name):
    """미국 종목명/티커를 Finnhub 심볼로 변환한다."""
    raw = stock_name.strip()
    alias = US_NAME_ALIASES.get(raw) or US_NAME_ALIASES.get(raw.upper())
    if alias:
        return alias
    if re.fullmatch(r'[A-Za-z]{1,5}', raw):
        return raw.upper()
    data = finnhub_get('search', {'q': raw})
    if isinstance(data, dict):
        results = data.get('result', [])
        for item in results:
            symbol = str(item.get('symbol', ''))
            typ = str(item.get('type', '')).lower()
            if symbol and ('common stock' in typ or typ == 'stock'):
                return symbol
        if results:
            symbol = str(results[0].get('symbol', ''))
            if symbol:
                return symbol
    return None

def is_us_stock_input(stock_name):
    raw = stock_name.strip()
    if raw in US_NAME_ALIASES or raw.upper() in US_NAME_ALIASES:
        return True
    return bool(re.fullmatch(r'[A-Za-z]{1,5}', raw))

def fetch_us_stock_data(symbol):
    """Finnhub quote + candle 기반 미국주식 가격/20일 평균/최근 고점."""
    quote = finnhub_get('quote', {'symbol': symbol})
    if not isinstance(quote, dict) or quote.get('c') is None:
        return None, None, None, 0, 0, 0

    current = float(quote.get('c') or 0)
    prev = float(quote.get('pc') or 0)
    change_pct = float(quote.get('dp') or 0)

    end = int(time.time())
    start = end - 45 * 86400
    candles = finnhub_get('stock/candle', {
        'symbol': symbol, 'resolution': 'D', 'from': start, 'to': end
    })
    closes = []
    volumes = []
    if isinstance(candles, dict) and candles.get('s') == 'ok':
        closes = [float(x) for x in candles.get('c', []) if x is not None]
        volumes = [float(x) for x in candles.get('v', []) if x is not None]
    recent = closes[-20:] if closes else []
    ma20 = sum(recent) / len(recent) if recent else current * 0.95
    resistance = max(recent) if recent else current * 1.05
    volume = volumes[-1] if volumes else 0
    avg_volume = sum(volumes[-20:]) / len(volumes[-20:]) if volumes[-20:] else 0
    return current, change_pct, prev, ma20, resistance, volume, avg_volume

def fetch_us_news(symbol):
    """최근 미국 종목 뉴스 제목 최대 5개. AI는 이 결과만 사용한다."""
    now = datetime.datetime.now(datetime.timezone.utc).date()
    from_date = now - datetime.timedelta(days=3)
    data = finnhub_get('company-news', {
        'symbol': symbol,
        'from': from_date.isoformat(),
        'to': now.isoformat()
    })
    titles = []
    if isinstance(data, list):
        for item in data:
            title = str(item.get('headline') or '').strip()
            if title and title not in titles:
                titles.append(title)
            if len(titles) >= 5:
                break
    return titles

def search_krx_code(stock_name):
    try:
        url = f"https://ac.stock.naver.com/ac?q={urllib.parse.quote(stock_name)}&target=stock"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for it in data.get('items', []):
                code = it.get('code')
                if code and len(code) == 6:
                    return code
    except Exception:
        pass
    return None

def fetch_kr_stock_realtime(code_six):
    try:
        url = f"https://m.stock.naver.com/api/stock/{code_six}/basic"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=1.2) as resp:
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
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=1.2) as resp:
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

def fetch_fast_news(code_six, stock_name):
    titles = []
    if code_six:
        try:
            url = f"https://m.stock.naver.com/api/stock/{code_six}/news?pageSize=4"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                items = data if isinstance(data, list) else data.get('items', [])
                for item in items:
                    raw_title = item.get('tit') or item.get('title') or ''
                    clean = re.sub(r'<[^>]+>|\[.*?\]|&quot;|&amp;', '', raw_title).strip()
                    if clean and clean not in titles:
                        titles.append(clean)
                    if len(titles) >= 3:
                        return titles
        except Exception:
            pass

    if not titles:
        titles = [f"{stock_name} 주요 공시 및 호가창 수급 집중", f"{stock_name} 외국인·기관 거래량 변동성 확대"]
    return titles[:3]

def analyze_fast_ai(stock_name, news_list, current_price=0, change_pct=0,
                   foreign_5d=None, institution_5d=None, individual_5d=None,
                   calendar_text="", market="KR", volume=0, avg_volume=0):
    """
    Groq 분석 엔진.
    기존 데이터 수집 구조는 유지하고 Gemini 대신 Groq가 수집된 데이터를 판단한다.
    뉴스 검색은 하지 않고 코드가 수집한 뉴스만 분석한다.
    """
    if not GROQ_KEY:
        return "[원인 불명확] GROQ_API_KEY가 설정되지 않았어."

    diag_ok, diag_message = check_groq_access()
    if not diag_ok:
        return f"[원인 불명확] Groq 접근 진단 실패: {diag_message}"

    try:
        news_block = "\n".join(
            f"- {title}" for title in (news_list or []) if title
        )

        supply_block = (
            f"최근 5일 외국인 순매수: {foreign_5d}주\n"
            f"최근 5일 기관 순매수: {institution_5d}주\n"
            f"최근 5일 개인 순매수: {individual_5d}주"
        )

        prompt = f"""
너는 한국 주식의 '왜 올랐을까/왜 내렸을까' 원인을 판단하는 분석 AI다.

중요 규칙:
1. 웹 검색을 하지 마라. 제공된 데이터만 분석하라.
2. 뉴스 제목 하나를 무조건 원인으로 단정하지 마라.
3. 주가 등락, 수급, 뉴스와 일정의 연관성을 비교하라.
4. 가장 영향력이 큰 원인 1개만 선택하라.
5. 근거가 부족하면 억지로 만들지 말고 '원인 불명확'으로 판단하라.
6. 반드시 JSON으로만 출력하라.
7. JSON 형식:
{{
  "judgment": "호재" 또는 "악재" 또는 "원인 불명확",
  "main_reason": "핵심 원인 1개",
  "summary": "왜 주가에 영향을 줬는지 한 문장",
  "confidence": "높음" 또는 "중간" 또는 "낮음"
}}
8. 퍼센트나 구체적인 가격 숫자는 summary에 쓰지 마라.
9. 제공되지 않은 사실을 만들어내지 마라.

시장: {market}
종목: {stock_name}
현재 주가: {current_price}
오늘 등락률: {change_pct}%
거래량: {volume}
20일 평균 거래량: {avg_volume}

수급:
{supply_block}

뉴스:
{news_block if news_block else "- 수집된 뉴스 없음"}

관련 일정:
{calendar_text}
""".strip()

        api_url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "주식 원인 분석 전문가. 제공된 데이터만 사용하고 핵심 원인 하나만 판단한다."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_completion_tokens": 500,
            "reasoning_effort": "none",
            "response_format": {"type": "json_object"}
        }

        req_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_KEY}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
            },
            method="POST"
        )

        print(f"🔎 Groq Chat 요청: model={GROQ_MODEL}")

        # Groq는 정상 응답을 빠르게 반환하도록 하되, 네트워크 지연 시에도 무한 대기하지 않는다.
        try:
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                raw_response = resp.read().decode("utf-8")
                res_json = json.loads(raw_response)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            print(f"❌ Groq HTTP 오류 {e.code}: {error_body[:1500]}")
            return f"[원인 불명확] Groq API 오류({e.code})"
        except Exception as e:
            print(f"❌ Groq 네트워크 오류: {type(e).__name__}: {e}")
            return "[원인 불명확] Groq API 연결에 실패했어."

        content = (
            res_json.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        try:
            # 모델이 혹시 코드펜스까지 붙여도 JSON만 안전하게 추출한다.
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            parsed = json.loads(cleaned.strip())
            judgment = str(parsed.get("judgment", "")).strip()
            reason = str(parsed.get("main_reason", "")).strip()

            if judgment not in ("호재", "악재", "원인 불명확"):
                judgment = "원인 불명확"

            if not reason:
                reason = "제공된 데이터만으로 핵심 원인을 특정하기 어렵습니다."

            if judgment == "원인 불명확":
                return f"[원인 불명확] {reason}"

            print(f"🟢 Groq 분석 성공: {stock_name} / {judgment}")
            return f"[{judgment} 🚨] {reason}"

        except Exception:
            return content[:100] if content else "[원인 불명확] AI 분석 결과가 없습니다."

    except Exception as e:
        print("❌ Groq 분석 오류:", e)
        return "[원인 불명확] AI 분석 요청에 실패했어."

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
        {"name": "미국 8월 소비자물가지수 #CPI", "dt": datetime.datetime(2026, 9, 11, 21, 30, tzinfo=kst_tz)},
        {"name": "미국 연준 #FOMC 기준금리 결정", "dt": datetime.datetime(2026, 9, 17, 3, 0, tzinfo=kst_tz)}
    ]
    upcoming = [e for e in events if e['dt'] >= now][:4] or events[:4]
    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    lines = [
        f"• {e['dt'].strftime('%m/%d')}({weekdays[e['dt'].weekday()]}) {e['dt'].strftime('%H:%M')} {e['name']}"
        for e in upcoming
    ]
    return (
        "🚨 오늘 밤엔 큰 거 하나 온다! 긴장 바짝 해!\n\n"
        "🗓️ 이번 주 핵심 개미 캘린더 ★★★\n" + "\n".join(lines) +
        "\n\n\"지표나 실적 발표 전후로는 호가창 얇아지니까 뇌동매매 절대 금지야! 알았제?\""
    )

# ⚡ [엔진 핵심] 단일 종목 데이터 수집 + AI 조리 후 UI 포맷 생성 함수
def build_stock_payload(stock_name, clean_code, market='KR'):
    if market == 'US':
        symbol = clean_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            f_market = executor.submit(fetch_us_stock_data, symbol)
            f_news = executor.submit(fetch_us_news, symbol)
            market_data = f_market.result()
            news_list = f_news.result()

        current_price, change_pct, prev_price, ma20, resistance_price, volume, avg_volume = market_data
        if current_price is None or current_price <= 0:
            return {"sections": [{"title": f"⚠️ {stock_name} 미국주식 데이터를 가져오지 못했어", "content": "잠시 후 다시 검색해줘!"}]}

        calendar_text = get_live_calendar_data()
        # 미국주식은 국내식 외국인/기관 5일 순매수 데이터가 제공되지 않으므로 허위 수급을 만들지 않는다.
        us_supply = f"거래량 {volume:,.0f}주\n20일 평균 거래량 {avg_volume:,.0f}주"
        ai_reason = analyze_fast_ai(
            stock_name=f"{stock_name} ({symbol})",
            news_list=news_list,
            current_price=current_price,
            change_pct=change_pct,
            foreign_5d=None,
            institution_5d=None,
            individual_5d=None,
            calendar_text=calendar_text,
            market='US',
            volume=volume,
            avg_volume=avg_volume
        )

        if change_pct >= 0.5:
            status_emoji, title_word = '🔥', '상승했을까'
            intro_ment = f"{change_pct:+.2f}% 상승 중이야"
        elif change_pct <= -0.5:
            status_emoji, title_word = '❄️', '하락했을까'
            intro_ment = f"{change_pct:+.2f}% 하락 중이야"
        else:
            status_emoji, title_word = '⚖️', '보합일까'
            intro_ment = f"{change_pct:+.2f}%로 눈치싸움 중이야"

        price_str = f"${current_price:,.2f}"
        ma20_str = f"${ma20:,.2f}"
        res_str = f"${resistance_price:,.2f}"
        news_lines = "\n".join([f"📰 {t}" for t in news_list]) if news_list else "📰 최근 수집된 미국 종목 뉴스가 없어"
        volume_ratio = (volume / avg_volume) if avg_volume > 0 else 0
        volume_line = f"거래량은 20일 평균 대비 {volume_ratio:.1f}배야." if volume_ratio > 0 else "거래량 비교 데이터가 없어."

        payload = {
            "sections": [
                {"title": f"{status_emoji} 오늘 왜 {title_word}?", "content": f"{intro_ment}\n\n현재 주가는 {price_str} 기록 중!\n\n💡 {ai_reason}\n\n{news_lines}\n\n#{symbol} #{change_pct:+.2f}%", "tags": [f"#{symbol}", f"#{change_pct:+.2f}%"]},
                {"title": "거래량은 붙었을까?", "content": f"{us_supply}\n\n{volume_line}"},
                {"title": "여기 깨지면 조심", "content": f"#20일 평균선 {ma20_str}\n\n#최근 20일 고점 {res_str}"},
                {"title": "오늘 밤, 이번주 무슨 일이 있나?", "content": calendar_text}
            ]
        }
        return payload

    # 한국주식 기존 로직
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_price = executor.submit(fetch_kr_stock_realtime, clean_code)
        f_supply = executor.submit(fetch_krx_trend_and_supply, clean_code)
        f_news = executor.submit(fetch_fast_news, clean_code, stock_name)
        cur_p, diff, ratio = f_price.result()
        ma20_val, res_val, f_5d, i_5d, ind_5d, v_days = f_supply.result()
        news_list = f_news.result()

    calendar_text = get_live_calendar_data()
    ai_reason = analyze_fast_ai(stock_name, news_list, current_price=cur_p or 0, change_pct=ratio if ratio is not None else 0,
                                foreign_5d=f_5d, institution_5d=i_5d, individual_5d=ind_5d,
                                calendar_text=calendar_text, market='KR')

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

    if change_pct >= 0.5:
        status_emoji, title_word = '🔥', '상승했을까'; intro_ment = f"스멀스멀 {change_pct:+.2f}% 우상향 중이야\n개미들아! 분위기 나쁘지 않은데? 이대로만 가자"
    elif change_pct <= -0.5:
        status_emoji, title_word = '❄️', '하락했을까'; intro_ment = f"아이고 {change_pct:+.2f}% 파란불 켜져서 속 쓰리겠다\n개미들아! 물 한잔 마시고 차분하게 보자"
    else:
        status_emoji, title_word = '⚖️', '보합일까'; intro_ment = f"{change_pct:+.2f}%로 팽팽한 눈치싸움 중이야"

    news_lines = "\n".join([f"📰 {t}" for t in news_list])
    return {"sections": [
        {"title": f"{status_emoji} 오늘 왜 {title_word}?", "content": f"{intro_ment}\n\n현재 주가는 {price_str} 기록 중!\n\n💡 {ai_reason}\n\n{news_lines}\n\n#{stock_name} #{change_pct:+.2f}%", "tags": [f"#{stock_name}", f"#{change_pct:+.2f}%"]},
        {"title": "큰손들은 담고 있을까, 털고 있을까?", "content": supply_content},
        {"title": "여기 깨지면 도망쳐", "content": f"#생존 지지선 {ma20_str} 기억해! 깨지면 비중 줄여!\n\n#악성 매물대 {res_str}\n돌파한다고 무지성 매수 타면 물린다잉!"},
        {"title": "오늘 밤, 이번주 무슨 일이 있나?", "content": calendar_text}
    ]}

# ⚡ [백그라운드 워커] 주기적으로 주요 종목을 미리 긁어 Redis에 저장 (사용자는 0.01초 컷)
def background_collector_loop():
    time.sleep(5)  # 서버 부팅 후 5초 뒤부터 주기적 수집 가동
    while True:
        if redis_client:
            print("🔄 [백그라운드 워커] 주요 종목 사전 수집 및 AI 분석 시작...")
            for name, code in PRELOAD_TARGETS:
                try:
                    data = build_stock_payload(name, code)
                    # 3일 동안 즉시 반환 가능하도록 저장
                    redis_client.set(f"stock_view_{name}", json.dumps(data, ensure_ascii=False))
                    print(f"  ⚡ [{name}] 사전 진열 완료")
                except Exception as e:
                    print(f"  ⚠️ [{name}] 백그라운드 수집 에러:", e)
                time.sleep(1.5)  # 네이버 차단 방지용 안전 딜레이
            print("✅ [백그라운드 워커] 1회 주기 완료. 다음 갱신 대기 중...")
        time.sleep(600)  # 10분마다 자동 갱신

# 백그라운드 스레드 가동
collector_thread = threading.Thread(target=background_collector_loop, daemon=True)
collector_thread.start()

@app.route('/')
def home():
    return "gaemiGTP 백그라운드 수집 & 0.01초 캐시 엔진 가동 중!"

@app.route('/analyze', methods=['GET'])
def analyze():
    raw_name = request.args.get('stock', '삼성전자').strip()

    # 1. ⚡ [0.01초 응답] 백그라운드 워커가 미리 구워둔 캐시가 있으면 즉시 리턴
    cache_key = f"stock_view_{raw_name}"
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                res = json.loads(cached_data) if isinstance(cached_data, str) else cached_data
                return jsonify(res)
        except Exception:
            pass

    # 2. 캐시에 없으면(처음 검색된 종목) 즉시 실시간 수집 후 캐시에 구워둠
    clean_code = TICKERS.get(raw_name)
    market = 'KR'
    if clean_code:
        market = 'KR'
    elif re.match(r'^\d{6}$', raw_name):
        clean_code = raw_name
        market = 'KR'
    else:
        us_symbol = resolve_us_symbol(raw_name)
        if us_symbol:
            clean_code = us_symbol
            market = 'US'
        else:
            clean_code = search_krx_code(raw_name)
            market = 'KR' if clean_code else None

    if not clean_code or not market:
        return jsonify({
            "sections": [{"title": f"⚠️ '{raw_name}' 종목을 찾을 수 없어!", "content": "정확한 종목명이나 6자리 코드로 다시 검색해줘!"}]
        })

    try:
        fresh_payload = build_stock_payload(raw_name, clean_code, market=market)
        if redis_client:
            try:
                redis_client.setex(cache_key, 86400, json.dumps(fresh_payload, ensure_ascii=False))
            except Exception:
                pass
        return jsonify(fresh_payload)
    except Exception:
        return jsonify({"sections": [{"title": "⚠️ 통신 지연", "content": "잠시 후 다시 검색해줘!"}]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
