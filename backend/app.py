import os
from pathlib import Path
from flask import Flask, send_from_directory
from flask_cors import CORS

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)
application = app

from backend.routes.api import bp as api_bp
app.register_blueprint(api_bp)

# Static assets are served by Flask from frontend/. The API routes remain same-origin.
@app.get("/health")
def health():
    return {"ok": True, "service": "gaemiGTP"}

try:
    from backend.services import warmup
    warmup.start()
except Exception as exc:
    print(f"[워밍업] 초기화 실패: {type(exc).__name__}: {exc}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
