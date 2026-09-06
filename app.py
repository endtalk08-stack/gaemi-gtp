from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf

app = Flask(__name__)
CORS(app)

# 종목명과 주식 코드(티커)를 연결해주는 사전
TICKERS = {
    '삼성전자': '005930.KS',
    'SK하이닉스': '000660.KS',
    '알테오젠': '196170.KQ',
    '카카오': '035720.KS',
    '엔비디아': 'NVDA',
    '비트코인': 'BTC-USD'
}

@app.route('/analyze', methods=['GET'])
def analyze():
    stock_name = request.args.get('stock', 'SK하이닉스')
    ticker_symbol = TICKERS.get(stock_name)

    # 사전에 없는 종목을 검색했을 때
    if not ticker_symbol:
        return jsonify({
            "title": f"🤔 {stock_name} 데이터 준비 중",
            "content": "현재 실시간 연동이 지원되지 않는 종목입니다.\n조만간 더 많은 종목의 데이터를 긁어올 수 있도록 엔진을 업그레이드할 예정입니다!",
            "tags": ["#업데이트예정"]
        })

    try:
        # 야후 파이낸스에서 실시간 주가 데이터 긁어오기 (최근 2일치)
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="2d")
        
        if len(hist) >= 2:
            prev_close = hist['Close'].iloc[0] # 어제 종가
            current_price = hist['Close'].iloc[1] # 오늘 현재가
        else:
            prev_close = hist['Close'].iloc[0]
            current_price = hist['Close'].iloc[0]

        # 등락률 계산
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        # 상승/하락에 따른 반응 분기
        if change_pct > 0:
            trend = "상승"
            emoji = "🔥"
            tag1 = "#가즈아"
        elif change_pct < 0:
            trend = "하락"
            emoji = "❄️"
            tag1 = "#방어력테스트"
        else:
            trend = "보합"
            emoji = "🤔"
            tag1 = "#눈치보기"

        # 한국 주식은 원화(₩), 미국 주식/코인은 달러($) 표시
        currency = "$" if ticker_symbol in ['NVDA', 'BTC-USD'] else "₩"
        price_str = f"{currency}{current_price:,.0f}" if currency == "₩" else f"{currency}{current_price:,.2f}"

        title = f"{emoji} {stock_name}, 현재 {trend} 중!"
        content = f"현재 실시간 주가는 {price_str} ({change_pct:+.2f}%)를 기록하고 있어!\n\nAI 알고리즘이 야후 파이낸스 데이터를 스캔한 결과, 글로벌 매크로 지표에 따라 세력들의 알고리즘 매매가 치열하게 돌아가는 중이야. 꽉 잡아!"
        tags = [tag1, "#실시간주가연동", f"#{stock_name}"]

        return jsonify({
            "title": title,
            "content": content,
            "tags": tags
        })

    except Exception as e:
        return jsonify({
            "title": "🚨 통신 지연",
            "content": "주가 서버(Yahoo Finance) 접속에 병목이 발생했습니다.\n잠시 후 다시 검색해주세요.",
            "tags": ["#서버혼잡"]
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
