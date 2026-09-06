from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re

app = Flask(__name__)
CORS(app)

TICKERS = {
    '삼성전자': '005930.KS',
    'SK하이닉스': '000660.KS',
    '알테오젠': '196170.KQ',
    '카카오': '035720.KS',
    '엔비디아': 'NVDA',
    '테슬라': 'TSLA',
    '애플': 'AAPL',
    '비트코인': 'BTC-USD'
}

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
    # 1차 시도: 네이버 증권 외국인/기관 매매동향 웹 표 파싱 (정밀 정규식)
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f'https://finance.naver.com/item/main.naver?code={code_six}'
        }
        url = f"https://finance.naver.com/item/frgn.naver?code={code_six}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            html = resp.read().decode('euc-kr', 'replace')
            
            # 날짜(YYYY.MM.DD)가 포함된 첫 번째 데이터 행 추출
            match = re.search(r'<tr[^>]*>\s*<td class="tc">\s*<span class="tah p10 gray03">\d{4}\.\d{2}\.\d{2}</span>.*?</tr>', html, re.DOTALL)
            if match:
                row_html = match.group(0)
                tds = row_html.split('<td')
                if len(tds) > 7:
                    # 6번째 칸: 기관, 7번째 칸: 외국인
                    inst_clean = re.sub(r'<[^>]+>', '', tds[6]).strip().replace(',', '').replace('+', '')
                    foreign_clean = re.sub(r'<[^>]+>', '', tds[7]).strip().replace(',', '').replace('+', '')
                    
                    if inst_clean and foreign_clean:
                        inst_val = int(inst_clean)
                        foreign_val = int(foreign_clean)
                        if inst_val != 0 or foreign_val != 0:
                            indiv_val = -(inst_val + foreign_val)
                            return indiv_val, foreign_val, inst_val
    except Exception:
        pass

    # 2차 시도: 다음(Daum) 증권 API (정확한 영문 키 매핑)
    try:
        url = f"https://finance.daum.net/api/investor/days?symbolCode=A{code_six}&page=1&perPage=1"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://finance.daum.net/'
        })
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if 'data' in data and len(data['data']) > 0:
                latest = data['data'][0]
                foreign_val = int(latest.get('foreignStraightPurchaseVolume', 0))
                inst_val = int(latest.get('institutionStraightPurchaseVolume', 0))
                indiv_val = int(latest.get('individualStraightPurchaseVolume', -(foreign_val + inst_val)))
                if foreign_val != 0 or inst_val != 0:
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

@app.route('/')
def home():
    return "gaemiGTP 수급 엔진 정상 가동 중!"

@app.route('/analyze', methods=['GET'])
def analyze():
    stock_name = request.args.get('stock', 'SK하이닉스').strip()
    ticker_symbol = TICKERS.get(stock_name, stock_name)

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1mo")
        if hist.empty: raise ValueError("데이터 없음")

        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) >= 2 else current_price
        change_pct = ((current_price - prev_close) / prev_close) * 100
        ma20 = hist['Close'].mean()

        currency = "$" if ('-' in ticker_symbol or not ticker_symbol.endswith(('.KS', '.KQ'))) else "₩"
        price_str = f"{currency}{current_price:,.0f}" if currency == "₩" else f"{currency}{current_price:,.2f}"
        ma20_str = f"{currency}{ma20:,.0f}" if currency == "₩" else f"{currency}{ma20:,.2f}"
        is_up = change_pct >= 0

        news_list = fetch_realtime_news(stock_name)
        main_news = news_list[0] if len(news_list) > 0 else f"{stock_name} 관련 메이저 재료 포착"
        sub_news = news_list[1] if len(news_list) > 1 else "기관·외국인 프로그램 매매 공방전"

        clean_code = ''.join(filter(str.isdigit, ticker_symbol))
        indiv, foreign, inst = (None, None, None)
        if len(clean_code) == 6:
            indiv, foreign, inst = fetch_krx_supply_demand(clean_code)

        # 수급 데이터가 유의미하게 존재하는 경우에만 팩트 체크 출력
        if foreign is not None and inst is not None and (foreign != 0 or inst != 0):
            foreign_str = format_shares(foreign)
            inst_str = format_shares(inst)
            indiv_str = format_shares(indiv)

            if foreign > 0 and inst > 0:
                flow_msg = "외인과 기관이 쌍끌이 순매수로 물량을 쓸어 담고 있어! 추가 상승 탄력 기대해볼 만해."
            elif foreign < 0 and inst < 0:
                flow_msg = "외인과 기관이 동반 차익 매도 중이야. 개인만 물량을 받아내고 있으니 무리한 추격매수는 조심해!"
            elif foreign > 0:
                flow_msg = "외국인 중심의 순매수가 들어오며 주가 하방을 탄탄하게 지지해 주고 있어."
            elif inst > 0:
                flow_msg = "기관 중심의 순매수가 들어오며 저가 물량을 영리하게 모아가는 흐름이야."
            else:
                flow_msg = "개인과 세력 간의 팽팽한 눈치싸움 공방전이 벌어지고 있어."

            supply_content = (
                f"🔥실시간 수급 팩트 체크:\n"
                f"• 외국인: {foreign_str}\n"
                f"• 기  관: {inst_str}\n"
                f"• 개  인: {indiv_str}\n\n"
                f"{flow_msg} 과연 전고점을 돌파할까? 두근두근"
            )
        else:
            supply_content = (
                f"🔥수급 레이더: 시장에서 \"{sub_news}\" 관련 세력 손바뀜이 활발해!\n"
                f"현재 주요 매물대 부근에서 치열한 공방전 진행 중. 과연 전고점을 뚫을까? 두근두근"
            )

        sections = [
            {
                "title": f"{'🔥' if is_up else '❄️'} 그래서 오늘은 왜 {'올랐어' if is_up else '숨고르기일까'}?",
                "content": f"개미들아! {stock_name} {change_pct:+.2f}% {'상승' if is_up else '하락'}중이야!!!\n현재 실시간 주가는 {price_str} 기록 중!\n\n오늘 터진 핵심 뉴스 헤드라인이야:\n📰 \"{main_news}\"\n이슈가 전해지면서 세력들의 매매가 요동치고 있어. 꽉 잡아!",
                "tags": [f"#{stock_name}", f"#{change_pct:+.2f}%", "#실시간속보"]
            },
            {
                "title": "지금 세력은 사고 있어, 팔고 있어?",
                "content": supply_content
            },
            {
                "title": "여기 깨지면 도망쳐라!",
                "content": f"🛡️생존 지지선: {ma20_str} (20일선 기준)\n이 가격 깨지면 투매 나오니까 절대 미련 갖지 말고 비중 줄여!\n🧱악성 매물대: 최근 고점 부근에 과거 물려있는 개미들의 본전 대기 물량이 쏟아질 수 있어 ㅠㅠ."
            },
            {
                "title": "🐜 오늘 밤, 내일 무슨 일이 있나?",
                "content": "📅주의 일정: 내일 주요 경제 지표 발표와 나스닥 선물 체크 필수!\n📝공시 체크: 대규모 보호예수 물량이나 시간외 단일가 움직임에 오버나잇(밤샘 보유) 주의해랔!"
            }
        ]
        return jsonify({"sections": sections})

    except Exception:
        return jsonify({"error": "데이터 지연"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
