from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/analyze', methods=['GET'])
def analyze():
    stock = request.args.get('stock', 'SK하이닉스')
    return jsonify({
        "stock": stock,
        "title": "오늘 왜 올랐을까?",
        "content": f"{stock} 관련 주요 공시 및 수급을 종합한 결과,\n외국인·기관 중심의 강한 매수세가 유입되었습니다.",
        "tags": ["#공급계약", "#외인순매수"]
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
