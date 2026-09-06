from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf

app = Flask(__name__)
CORS(app)

TICKERS = {
    '삼성전자': '005930.KS',
    'SK하이닉스': '000660.KS',
    '알테오젠': '196170.KQ',
    '카카오': '035720.KS',
    '엔비디아': 'NVDA',
    '비트코인': 'BTC-USD'
}

@app.route('/')
def home():
    return "gaemiGTP 백엔드 엔진이 정상 가동 중입니다!"

@app.route('/analyze', methods=['GET'])
def analyze():
    stock_name = request.args.get('stock', 'SK하이닉스').strip()
    ticker_symbol = TICKERS.get(stock_name, stock_name)

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1mo")
        if hist.empty:
            raise ValueError("데이터 없음")

        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) >= 2 else current_price
        change_pct = ((current_price - prev_close) / prev_close) * 100
        ma20 = hist['Close'].mean()

        currency = "$" if ('-' in ticker_symbol or not ticker_symbol.endswith(('.KS', '.KQ'))) else "₩"
        price_str = f"{currency}{current_price:,.0f}" if currency == "₩" else f"{currency}{current_price:,.2f}"
        ma20_str = f"{currency}{ma20:,.0f}" if currency == "₩" else f"{currency}{ma20:,.2f}"

        is_up = change_pct >= 0
        sections = [
            {
                "title": f"{'🔥' if is_up else '❄️'} 그래서 오늘은 왜 {'올랐어' if is_up else '숨고르기일까'}?",
                "content": f"개미들아! {stock_name} {change_pct:+.2f}% {'상승' if is_up else '하락'}중이야!!!\n현재 실시간 주가는 {price_str} 기록 중!\n\n최근 글로벌 지표와 수급에 따라 세력들의 알고리즘 매매가 치열하게 돌아가는 중이야. 꽉 잡아!",
                "tags": [f"#{stock_name}", f"#{change_pct:+.2f}%", "#실시간주가"]
            },
            {
                "title": "지금 세력은 사고 있어, 팔고 있어?",
                "content": "🔥수급 경고: 최근 개인과 외국인의 눈치싸움이 치열해!\n현재 기관 추정 매수 단가 부근에서 공방전이 벌어지고 있어. 과연 고점을 돌파할까? 두근두근"
            },
            {
                "title": "여기 깨지면 도망쳐라!",
                "content": f"🛡️생존 지지선: {ma20_str} (20일선)\n이 가격이 깨지면 투매가 나올 수 있으니 조심해야 해!\n🧱악성 매물대: 최근 단기 고점 부근에 과거 물려있는 개미들의 본전 대기 물량이 쏟아질 수 있어 ㅠㅠ."
            },
            {
                "title": "🐜 오늘 밤, 내일 무슨 일이 있나?",
                "content": "📅주의 일정: 내일(목) 주요 경제 지표 발표가 대기 중이네!\n📝공시 체크: 대규모 보호예수 물량이나 시간외 단일가 움직임에 오버나잇(밤샘 보유) 주의해랔!"
            }
        ]
        return jsonify({"sections": sections})
    except Exception:
        return jsonify({"error": "데이터 지연"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
