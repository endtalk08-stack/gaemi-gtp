import os
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from backend.services.engine import analyze_stock, get_live_calendar_data, start_calendar_warmup

# 최상위 app.py 위치를 기준으로 frontend 폴더의 절대 경로를 설정합니다.
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path="",
)
CORS(app)

# 시장 일정은 서버 기동 직후 백그라운드에서 미리 갱신한다. /analyze를 지연시키지 않는다.
start_calendar_warmup()

application = app


@app.get("/")
def home():
    # 랜더 및 브라우저의 메인 접속 요청 시 frontend/index.html을 보냅니다.
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/admin")
def admin():
    # 관리자 페이지 요청 시 frontend/admin/index.html을 보냅니다.
    return send_from_directory(FRONTEND_DIR / "admin", "index.html")


@app.get("/health")
def health():
    # 랜더의 헬스체크(Health Check) 전용 라우트입니다.
    return jsonify({"ok": True, "service": "gaemiGTP"})


@app.get("/calendar")
def calendar():
    """실시간 시장 일정 확인용 엔드포인트."""
    return jsonify({"ok": True, "content": get_live_calendar_data("", "")})


@app.get("/analyze")
def analyze():
    stock = request.args.get("stock", "SK하이닉스")
    started = time.perf_counter()
    try:
        result = analyze_stock(stock)
        response = jsonify(result)
        response.headers["X-Analysis-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.0f}"
        return response
    except Exception as exc:
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
    # Render가 제공하는 PORT 환경 변수를 동적으로 바인딩하고 0.0.0.0으로 외부 접속을 허용합니다.
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)