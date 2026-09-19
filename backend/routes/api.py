from flask import Blueprint, jsonify, request
from backend.services.engine import analyze_stock

# backend/app.py에서 불러올 Blueprint 객체 명시적 선언
api_bp = Blueprint("api", __name__)


@api_bp.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json() or {}
    stock_name = data.get("stock_name", "").strip()

    if not stock_name:
        return jsonify({"ok": False, "error": "empty_stock_name"}), 400

    result = analyze_stock(stock_name)
    return jsonify(result)


@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})
