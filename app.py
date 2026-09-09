from flask import Flask, jsonify, request
from flask_cors import CORS
import urllib.request
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

# ⚡ [Groq API 키 적용]
GROQ_KEY = os.environ.get('GROQ_API_KEY', '').strip().strip('\'"')
REDIS_URL = os.environ.get('UPSTASH_REDIS_REST_URL')
REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
redis_client = None

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

# ⚡ [Groq LPU 초광속 추론] (0.08초 만에 생성 완료)
def analyze_fast_ai(stock_name, news_list):
    fallback_ment = "주요 공시와 호가창 매물대 흐름을 체크하며 방향성을 탐색 중이야."
    if not GROQ_KEY or not news_list:
        return fallback_ment

    try:
        news_block = "\n".join(news_list)
        prompt = (
            f"종목명: {stock_name}\n최신 뉴스:\n{news_block}\n\n"
            "위 내용을 바탕으로 반드시 '[호재 🚨]' 또는 '[악재 🚨]'로 시작해서, 구체적인 퍼센트(%)나 가격 숫자 없이 왜 그런지 주식 고수 개미 말투로 딱 한 줄(50자 이내)만 써."
        )

        api_url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "너는 한국 실전 주식 단타 베테랑 고수야. 간결하고 날카롭게 핵심만 말해."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 80
        }
        
        req_data = json.dumps(payload).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {GROQ_KEY}'
        }
        req = urllib.request.Request(api_url, data=req_data, headers=headers, method='POST')

        with urllib.request.urlopen(req, timeout=2.0) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            return res_json['choices'][0]['message']['content'].strip()
    except Exception as e:
        print("Groq API 호출 예외:", e)
        return fallback_ment

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
    lines = [f"• {e['dt'].strftime(f'%m/%d({weekdays[e[\"dt\"].weekday()]}) %H:%M')} {e['name']}" for e in upcoming]
    return (
        "🚨 오늘 밤엔 큰 거 하나 온다! 긴장 바짝 해!\n\n"
        "🗓️ 이번 주 핵심 개미 캘린더 ★★★\n" + "\n".join(lines) +
        "\n\n\"지표나 실적 발표 전후로는 호가창 얇아지니까 뇌동매매 절대 금지야! 알았제?\""
    )

def build_stock_payload(stock_name, clean_code):
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_price = executor.submit(fetch_kr_stock_realtime, clean_code)
        f_supply = executor.submit(fetch_krx_trend_and_supply, clean_code)
        f_news = executor.submit(fetch_fast_news, clean_code, stock_name)

        cur_p, diff, ratio = f_price.result()
        ma20_val, res_val, f_5d, i_5d, ind_5d, v_days = f_supply.result()
        news_list = f_news.result()

    ai_reason = analyze_fast_ai(stock_name, news_list)

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
        status_emoji, title_word = '🔥', '상승했을까'
        intro_ment = f"스멀스멀 {change_pct:+.2f}% 우상향 중이야\n개미들아! 분위기 나쁘지 않은데? 이대로만 가자"
    elif change_pct <= -0.5:
        status_emoji, title_word = '❄️', '하락했을까'
        intro_ment = f"아이고 {change_pct:+.2f}% 파란불 켜져서 속 쓰리겠다\n개미들아! 물 한잔 마시고 차분하게 보자"
    else:
        status_emoji, title_word = '⚖️', '보합일까'
        intro_ment = f"{change_pct:+.2f}%로 팽팽한 눈치싸움 중이야"

    news_lines = "\n".join([f"📰 {t}" for t in news_list])

    payload = {
        "sections": [
            {
                "title": f"{status_emoji} 오늘 왜 {title_word}?",
                "content": f"{intro_ment}\n\n현재 주가는 {price_str} 기록 중!\n\n💡 {ai_reason}\n\n{news_lines}\n\n#{stock_name} #{change_pct:+.2f}%",
                "tags": [f"#{stock_name}", f"#{change_pct:+.2f}%"]
            },
            {"title": "큰손들은 담고 있을까, 털고 있을까?", "content": supply_content},
            {"title": "여기 깨지면 도망쳐", "content": f"#생존 지지선 {ma20_str} 기억해! 깨지면 비중 줄여!\n\n#악성 매물대 {res_str}\n돌파한다고 무지성 매수 타면 물린다잉!"},
            {"title": "오늘 밤, 이번주 무슨 일이 있나?", "content": get_live_calendar_data()}
        ]
    }
    return payload

def background_collector_loop():
    time.sleep(5)
    while True:
        if redis_client:
            print("🔄 [백그라운드 워커] 주요 종목 Groq 초고속 수집/분석 시작...")
            for name, code in PRELOAD_TARGETS:
                try:
                    data = build_stock_payload(name, code)
                    redis_client.set(f"stock_view_{name}", json.dumps(data, ensure_ascii=False))
                    print(f"  ⚡ [{name}] Groq 사전 진열 완료")
                except Exception as e:
                    print(f"  ⚠️ [{name}] 백그라운드 수집 에러:", e)
                time.sleep(1.0)
            print("✅ [백그라운드 워커] 1회 주기 완료.")
        time.sleep(600)

collector_thread = threading.Thread(target=background_collector_loop, daemon=True)
collector_thread.start()

@app.route('/')
def home():
    return "gaemiGTP Groq 초고속 LPU 엔진 가동 중!"

@app.route('/analyze', methods=['GET'])
def analyze():
    raw_name = request.args.get('stock', '삼성전자').strip()

    # 1. ⚡ [0.01초 반환] 백그라운드가 구워둔 캐시 즉시 리턴
    cache_key = f"stock_view_{raw_name}"
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                res = json.loads(cached_data) if isinstance(cached_data, str) else cached_data
                return jsonify(res)
        except Exception:
            pass

    # 2. 신규 검색 종목 즉시 Groq 호출
    clean_code = TICKERS.get(raw_name)
    if not clean_code:
        if re.match(r'^\d{6}$', raw_name):
            clean_code = raw_name
        else:
            clean_code = search_krx_code(raw_name)

    if not clean_code:
        return jsonify({
            "sections": [{"title": f"⚠️ '{raw_name}' 종목을 찾을 수 없어!", "content": "정확한 종목명이나 6자리 코드로 다시 검색해줘!"}]
        })

    try:
        fresh_payload = build_stock_payload(raw_name, clean_code)
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
