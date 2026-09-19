import os
from flask import Flask, send_from_directory
from backend.routes.api import api_bp

app = Flask(__name__, static_folder="../frontend", static_url_path="")

# API 라우트 등록
app.register_blueprint(api_bp, url_prefix="/api")


@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/<path:path>")
def serve_static(path):
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
