from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from backend.services.engine import analyze_stock

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path="",
)
CORS(app)
application = app


@app.get("/")
def home():
    # Render/브라우저의 첫 요청은 실제 gaemiGTP 화면을 반환한다.
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "gaemiGTP"})


@app.get("/analyze")
def analyze():
    stock = request.args.get("stock", "SK하이닉스")
    try:
        result = analyze_stock(stock)
        return jsonify(result)
    except Exception as exc:
        # 엔진에서 이미 안전 복구를 하지만, 라우트 레벨에서도 JSON 오류로 감싼다.
        print(f"[API /analyze] unexpected error: {type(exc).__name__}: {exc}")
        return jsonify({
            "sections": [],
            "news_items": [],
            "disclosures": [],
            "us_filings": [],
            "ok": False,
            "error": "analysis_failed",
        }), 200


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
