"""Isolated, authenticated two-model prompt lab for the DigitalOcean AI settings.

No news collection, Neon writes, worker scheduling, or production AI changes.
The default prompts/model parameters reflect read-only inspection of the live
DigitalOcean worker on 2026-10-27 (not the potentially older ops-branch files).
Provider requests run independently on Render with its configured Groq key.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from flask import Blueprint, jsonify, request

from .ai_test import _authorized

worker_ai_lab_bp = Blueprint("worker_ai_lab", __name__)

ISSUE_PROMPT = (
    '제공된 종목의 뉴스 원문을 분석해 주가에 영향을 줄 중요한 상승 재료와 하락 재료를 합쳐서 0~3개 선정해.\n'
    '각 재료는 상승 재료이면 direction="up", 하락 재료이면 direction="down"으로 표기해. 어느 한쪽 재료가 없으면 만들지 마.\n'
    '제목은 핵심만 짧게, 내용은 쉽게 구체적으로, 해시태그 1개. 친구처럼 반말로 답변해.\n'
    '한국어 JSON 객체만 반환해:\n'
    '{"issues":[{"headline":"재료 제목","summary":"쉽고 구체적인 내용","direction":"up","tags":["#핵심키워드"],"source_ids":[1]}]}'
)

# Do not import or invoke the actual closing publisher: it reserves/publishes DB rows.
# Main-branch source is checked against the live DO values before shipping the lab.
from .us_market_close import MODEL as CLOSE_MODEL, US_CLOSE_PROMPT, US_CLOSE_QUESTION

CONFIG = {
    "issue": {
        "label": "AI 이슈 분석",
        "model": "openai/gpt-oss-20b",
        "system_prompt": ISSUE_PROMPT,
        "max_completion_tokens": 1000,
        "response_format": "json_object",
        "example_input": json.dumps({
            "stock": "테슬라",
            "news": [{
                "source_id": 1,
                "title": "[실제 기사 제목으로 교체]",
                "content": "[실제 기사 원문으로 교체]",
                "published_at": "[실제 기사 발행 시각으로 교체]",
            }],
        }, ensure_ascii=False, indent=2),
    },
    "close": {
        "label": "미국 마감시황",
        "model": CLOSE_MODEL,
        "system_prompt": US_CLOSE_PROMPT,
        "max_completion_tokens": 1500,
        "response_format": "free_text",
        "example_input": "참고 데이터(JSON):\n" + json.dumps({
            "session_date_et": "YYYY-MM-DD",
            "market_indices": [
                {"name": "다우존스", "close": None, "change_pct": None},
                {"name": "나스닥 종합", "close": None, "change_pct": None},
                {"name": "S&P 500", "close": None, "change_pct": None},
            ],
            "news": [
                {"source_id": 1, "title": "[실제 기사 제목]", "description": "[검증된 원문 내용]"},
                {"source_id": 2, "title": "[실제 기사 제목]", "description": "[검증된 원문 내용]"},
            ],
        }, ensure_ascii=False, indent=2) + "\n\n질문: " + US_CLOSE_QUESTION,
    },
}


def _allowed():
    # Reuse the established /ai-test administrator bearer token and feature flag.
    return _authorized()


def _token_usage(result):
    usage = result.get("usage") if isinstance(result, dict) else None
    if not isinstance(usage, dict):
        return {}
    measured = {
        name: usage[name]
        for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        if type(usage.get(name)) is int and usage[name] >= 0
    }
    details = usage.get("completion_tokens_details")
    if isinstance(details, dict) and type(details.get("reasoning_tokens")) is int:
        measured["reasoning_tokens"] = details["reasoning_tokens"]
    return measured


@worker_ai_lab_bp.get("/api/worker-ai-test/config")
def lab_config():
    if not _allowed():
        return jsonify({"ok": False, "error": "unauthorized_or_disabled"}), 403
    return jsonify({"ok": True, "models": CONFIG,
                    "mode": "independent_test_only",
                    "provider": "Render Groq key; identical live DO model/prompt defaults"})


@worker_ai_lab_bp.post("/api/worker-ai-test/run")
def lab_run():
    if not _allowed():
        return jsonify({"ok": False, "error": "unauthorized_or_disabled"}), 403
    if (request.content_length or 0) > 25000:
        return jsonify({"ok": False, "error": "request_too_large"}), 413
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "invalid_json"}), 400
    variant = data.get("variant")
    if variant not in CONFIG:
        return jsonify({"ok": False, "error": "invalid_model"}), 400
    config = CONFIG[variant]
    system_prompt = data.get("system_prompt", config["system_prompt"])
    user_input = data.get("user_input")
    if (not isinstance(system_prompt, str) or not isinstance(user_input, str)
            or not system_prompt.strip() or not user_input.strip()
            or len(system_prompt) > 6000 or len(user_input) > 15000):
        return jsonify({"ok": False, "error": "invalid_prompt"}), 400
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return jsonify({"ok": False, "error": "provider_not_configured"}), 503
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        "temperature": 0.2,
        "max_completion_tokens": config["max_completion_tokens"],
        "reasoning_effort": "low",
        "stream": False,
    }
    if variant == "issue":
        payload["response_format"] = {"type": "json_object"}
    provider_request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json",
                 "User-Agent": "gaemiGTP-isolated-worker-ai-test/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(provider_request, timeout=35) as response:
            result = json.loads(response.read().decode("utf-8"))
        choices = result.get("choices") or []
        choice = choices[0] if choices else {}
        answer = (choice.get("message") or {}).get("content")
        if not isinstance(answer, str) or not answer.strip():
            return jsonify({"ok": False, "error": "empty_provider_response"}), 502
        # Expose provider-reported counts, not approximated token estimates.
        return jsonify({"ok": True, "model": config["model"], "variant": variant,
                        "answer": answer, "usage": _token_usage(result),
                        "finish_reason": choice.get("finish_reason")})
    except urllib.error.HTTPError as exc:
        # Do not include upstream response bodies (they can contain private details).
        status = exc.code
        print("[worker-ai-lab] provider_http_error", variant, status, flush=True)
        return jsonify({"ok": False, "error": "provider_rate_limit" if status == 429
                        else "provider_http_error", "provider_status": status}), 429 if status == 429 else 502
    except (urllib.error.URLError, TimeoutError, ValueError, TypeError, KeyError, IndexError) as exc:
        print("[worker-ai-lab] provider_error", variant, type(exc).__name__, flush=True)
        return jsonify({"ok": False, "error": "provider_error"}), 502
