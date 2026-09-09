import datetime
import json
import math
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf

app = Flask(__name__)
CORS(app)

FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '').strip().strip('\'"')

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

def search_krx_code(stock_name):
    try:
        url = f"https://ac.finance.naver.com/ac?q={urllib.parse.quote(stock_name)}&q_enc=utf-8&st=1&r_lt=1&r_format=json&r_enc=utf-8"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            items = res_json.get('items', [])
            if items and len(items[0]) > 0:
                first = items[0][0]
                code = first[0]
                market = first[3].upper()
                suffix = '.KS' if 'KOSPI' in market else '.KQ'
                return f"{code}{suffix}", code
    except Exception as e:
        app.logger.warning(f"KRX 자동완성 실패 ({stock_name}): {e}")
    return None, None

def fetch_kr_stock_realtime(code_six):
    try:
        url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code_six}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
            'Referer': 'https://m.stock.naver.com/'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            datas = data.get('datas', [])
            if datas:
                item = datas[0]
                cur_p = float(str(item.get('closePrice', 0)).replace(',', ''))
                diff = float(str(item.get('compareToPreviousClosePrice', 0)).replace(',', ''))
                ratio = float(str(item.get('fluctuationsRatio', 0)).replace(',', ''))
                return cur_p, diff, ratio
    except Exception as e:
        app.logger.warning(f"네이버 실시간 시세 예외 ({code_six}): {e}")
    return None, None, None

def fetch_krx_trend_and_supply(code_six):
    try:
        url = f"https://m.stock.naver.com/api/stock/{code_six}/trend?page=1&pageSize=20"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
            'Referer': 'https://m.stock.naver.com/'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and isinstance(data, list):
                prices = [float(str(r['closePrice']).replace(',', '')) for r in data if r.get('closePrice')]
                ma20 = sum(prices) / len(prices) if prices else 0
                resistance = max(prices) if prices else 0

                sum_foreign = sum(int(str(r.get('foreignerPureBuyQuant') or 0).replace(',', '')) for r in data[:5])
                sum_inst = sum(int(str(r.get('organPureBuyQuant') or r.get('institutionPureBuyQuant') or 0).replace(',', '')) for r in data[:5])
                sum_indiv = sum(int(str(r.get('individualPureBuyQuant') or 0).replace(',', '')) for r in data[:5])

                if sum_indiv == 0 and (sum_foreign != 0 or sum_inst != 0):
                    sum_indiv = -(sum_foreign + sum_inst)

                return ma20, resistance, sum_foreign, sum_inst, sum_indiv, min(len(data), 5)
    except Exception as e:
        app.logger.warning(f"네이버 수급 집계 예외 ({code_six}): {e}")
    return 0, 0, None, None, None, 0

def fetch_yahoo_direct_v8(ticker_str):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_str}?range=1mo&interval=1d"
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
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
        app.logger.warning(f"야후 v8 예외 ({ticker_str}): {e}")
    return None, None, None, None

def fetch_realtime_news(stock_name):
    try:
        query = urllib.parse.quote(stock_name)
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            root = ET.fromstring(resp.read())
            headlines = []
            for item in root.findall('.//item')[:3]:
                title_el = item.find('title')
                if title_el is not None and title_el.text:
                    title = re.sub(r'\[.*?\]|<[^>]+>|\s*[-–—―|]\s*[^-–—―|]+$|[\.…]+\s*$', '', title_el.text)
                    title = re.sub(r'\.{2,}|…', ' · ', title).strip().strip('"\'“”')
                    if title:
                        headlines.append(title)
            return headlines
    except Exception:
        return []

def format_shares(n):
    if n is None:
        return "0주"
    sign = "+" if n > 0 else ""
    if abs(n) >= 10000:
        return f"{sign}{n / 10000:,.1f}만주"
    return f"{sign}{n:,}주"

def round_krw_tick(price):
    if not price or math.isnan(price) or math.isinf(price) or price <= 0:
        return 0
    p = float(price)
    if p >= 500_000: return int(p // 1000) * 1000
    if p >= 200_000: return int(p // 500) * 500
    if p >= 50_000:  return int(p // 100) * 100
    if p >= 20_000:  return int(p // 50) * 50
    if p >= 5_000:   return int(p // 10) * 10
    if p >= 2_000:   return int(p // 5) * 5
    return int(p)

def get_live_calendar_data():
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_tz)
    weekdays = ['월', '화', '수', '목', '금', '토', '일']

    master_events = [
        {"name": "미국 생산자물가지수 #PPI", "dt": datetime.datetime(2026, 9, 10, 21, 30, tzinfo=kst_tz), "est": "0.2%", "type": "ppi"},
        {"name": "#오라클 ORCL 실적 발표", "dt": datetime.datetime(2026, 9, 11, 5, 0, tzinfo=kst_tz), "est": "예상 EPS $1.33", "type": "earnings", "target": "글로벌 AI·클라우드"},
        {"name": "#어도비 ADBE 실적 발표", "dt": datetime.datetime(2026, 9, 11, 5, 0, tzinfo=kst_tz), "est": "예상 EPS $6.08", "type": "earnings", "target": "글로벌 빅테크"},
        {"name": "미국 소비자물가지수 #CPI", "dt": datetime.datetime(2026, 9, 11, 21, 30, tzinfo=kst_tz), "est": "0.2%", "type": "cpi"},
        {"name": "미국 연준 #FOMC 기준금리 결정", "dt": datetime.datetime(2026, 9, 17, 3, 0, tzinfo=kst_tz), "est": "기준금리 3.50%~3.75%", "type": "fomc"},
        {"name": "미국 개인소비지출 #PCE 물가지수", "dt": datetime.datetime(2026, 9, 25, 21, 30, tzinfo=kst_tz), "est": "2.6%", "type": "pce"}
    ]

    master_events.sort(key=lambda x: x['dt'])
    upcoming = [ev for ev in master_events if ev['dt'] >= now_kst] or master_events[:4]

    tomorrow_morning = (now_kst + datetime.timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    tonight_event = next((ev for ev in upcoming if ev['dt'] <= tomorrow_morning), None)

    if tonight_event:
        t_dt = tonight_event['dt']
        time_str = t_dt.strftime(f"%m/%d({weekdays[t_dt.weekday()]}) %H:%M")
        if tonight_event['type'] == 'earnings':
            tonight_card = f"🚨 오늘 밤 빅이벤트!\n\n⏰ {time_str} {tonight_event['name']}\n{tonight_event.get('target')} 실적 발표! 미장 변동성이 국장 개장가에 영향을 주니 사전 점검 필수야."
        else:
            tonight_card = f"🚨 오늘 밤 주요 지표 발표!\n\n⏰ {time_str} {tonight_event['name']}\n시장 예상치는 {tonight_event['est']} 수준이야. 괴리율에 따른 야간 선물 변동에 유의하자."
    else:
        tonight_card = "🌙 오늘 밤은 주요 거시 이벤트 없음!\n장 마감 후 무리한 야간 베팅 대신 이번 주 후반부 예정된 지표 일정을 점검해 둬."

    check_lines = [f"• {ev['dt'].strftime(f'%m/%d({weekdays[ev[\"dt\"].weekday()]}) %H:%M')} {ev['name']}" for ev in upcoming[:4]]
    calendar_block = "🗓️ 이번 주 핵심 캘린더\n" + "\n".join(check_lines)

    return f"{tonight_card}\n\n{calendar_block}"

@app.route('/analyze', methods=['GET'])
def analyze():
    raw_name = request.args.get('stock', 'SK하이닉스').strip()
    ticker_symbol = TICKERS.get(raw_name)
    clean_code = None

    try:
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
            ticker_symbol = "000660.KS"
            clean_code = "000660"

        is_krw = ('-' not in ticker_symbol and ticker_symbol.endswith(('.KS', '.KQ'))) or bool(clean_code and len(clean_code) == 6)

        current_price, change_pct, ma20, resistance_price = 0.0, 0.0, 0.0, 0.0
        supply_content = ""

        # 1. 국내 주식 조회
        if is_krw and clean_code:
            cur_p, _, ratio = fetch_kr_stock_realtime(clean_code)
            ma20_val, res_val, f_5d, i_5d, ind_5d, v_days = fetch_krx_trend_and_supply(clean_code)

            if not cur_p:
                return jsonify({"error": f"{raw_name}의 실시간 가격 정보를 가져올 수 없습니다."}), 502

            current_price = cur_p
            change_pct = ratio or 0.0
            ma20 = ma20_val or current_price * 0.95
            resistance_price = res_val or current_price * 1.05

            price_str = f"{round_krw_tick(current_price):,}원"
            ma20_str = f"{round_krw_tick(ma20):,}원"
            res_str = f"{round_krw_tick(resistance_price):,}원"

            if f_5d is not None and i_5d is not None and v_days > 0:
                tag_line = f"#외국인 {format_shares(f_5d)} #기관 {format_shares(i_5d)} #개인 {format_shares(ind_5d)}"
                if f_5d > 0 and i_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일 외인·기관 쌍끌이 순매수! 세력이 하방을 지지하고 있어."
                elif f_5d < 0 and i_5d < 0:
                    supply_content = f"{tag_line}\n\n최근 5일 메이저 동반 순매도. 개미 매수세만 유입되니 분할 대응이 안전해."
                elif f_5d > 0:
                    supply_content = f"{tag_line}\n\n외국인 주도 순매수 장세. 단기 탄력 기대감이 유효해."
                elif i_5d > 0:
                    supply_content = f"{tag_line}\n\n기관 순매수 방어. 20일선 지지 확인 후 접근 추천."
                else:
                    supply_content = f"{tag_line}\n\n수급 공방 중. 방향성 확인 전까지 비중 조절 필요."

        # 2. 미국 주식 조회
        else:
            cur_p, prev_p, ma20_val, res_val = fetch_yahoo_direct_v8(ticker_symbol)
            if not cur_p or not prev_p:
                return jsonify({"error": f"{ticker_symbol}의 가격 데이터를 가져올 수 없습니다."}), 502

            current_price = cur_p
            change_pct = ((cur_p - prev_p) / prev_p) * 100
            ma20 = ma20_val or cur_p
            resistance_price = res_val or cur_p * 1.05

            price_str = f"${current_price:,.2f}"
            ma20_str = f"${ma20:,.2f}"
            res_str = f"${resistance_price:,.2f}"

            try:
                t_obj = yf.Ticker(ticker_symbol)
                opts = t_obj.options
                if opts:
                    chain = t_obj.option_chain(opts[0])
                    call_vol = int(chain.calls['volume'].fillna(0).sum())
                    put_vol = int(chain.puts['volume'].fillna(0).sum())
                    if call_vol > 0:
                        pc_ratio = put_vol / call_vol
                        c_str = f"{call_vol/10000:.1f}만건" if call_vol >= 10000 else f"{call_vol:,}건"
                        p_str = f"{put_vol/10000:.1f}만건" if put_vol >= 10000 else f"{put_vol:,}건"
                        tag_line = f"#콜 {c_str} #풋 {p_str} #비율 {pc_ratio:.2f}"

                        if pc_ratio <= 0.7:
                            supply_content = f"{tag_line}\n\n콜옵션 우세. 상방 베팅 유입 확인."
                        elif pc_ratio >= 1.1:
                            supply_content = f"{tag_line}\n\n풋옵션(하방 헤지) 증가. 주요 지지선 방어 확인 필수."
                        else:
                            supply_content = f"{tag_line}\n\n옵션 수급 중립. 지지/저항 라인 중심 박스권 대응 필요."
            except Exception as opt_err:
                app.logger.warning(f"옵션 체인 파싱 제외: {opt_err}")

        if not supply_content:
            supply_content = "수급 데이터 집계 지연\n20일 이동평균선을 주요 기준선으로 설정하고 대응하세요."

        # 3. 상태 분기
        if change_pct >= 5.0:
            emoji, word = '🔥', '급등했을까'
        elif change_pct >= 0.5:
            emoji, word = '📈', '상승했을까'
        elif change_pct > -0.5:
            emoji, word = '⚖️', '보합일까'
        elif change_pct > -5.0:
            emoji, word = '📉', '조정받을까'
        else:
            emoji, word = '❄️', '급락했을까'

        news_list = fetch_realtime_news(raw_name)
        news_lines = "\n".join([f"📰 \"{title}\"" for title in news_list]) if news_list else f"📰 \"{raw_name} 주요 뉴스 수집 중\""

        return jsonify({
            "sections": [
                {
                    "title": f"{emoji} 오늘은 왜 {word}?",
                    "content": f"현재가 {price_str} ({change_pct:+.2f}%)\n\n{news_lines}",
                    "tags": [f"#{raw_name}", f"#{change_pct:+.2f}%"]
                },
                {
                    "title": "큰손들은 담고 있을까, 털고 있을까?",
                    "content": supply_content
                },
                {
                    "title": "여기 깨지면 주의",
                    "content": f"• 기준 지지선: {ma20_str} (이탈 시 리스크 관리 권장)\n• 상단 저항선: {res_str} (단기 매물대 경계)"
                },
                {
                    "title": "주요 매크로 & 실적 캘린더",
                    "content": get_live_calendar_data()
                }
            ]
        })

    except Exception as e:
        app.logger.error(f"서버 처리 오류: {e}")
        return jsonify({"error": "데이터 처리 중 일시적인 오류가 발생했습니다."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
