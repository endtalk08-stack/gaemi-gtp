"""Small reversible development gate for gaemiGTP.

SITE_PRIVATE_MODE=1 enables the gate. Until a site password is configured
(falling back to the existing AI_TEST_TOKEN), requests fail closed.
SITE_PRIVATE_MODE=0 restores public mode without deleting site features.
"""
import hmac
import os
import threading
import time
from collections import defaultdict

from flask import jsonify, redirect, request, send_from_directory
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "gaemi_dev_access"
SESSION_TTL_SECONDS = 12 * 60 * 60
MAX_FAILURES_PER_WINDOW = 8
FAILURE_WINDOW_SECONDS = 10 * 60
_FAILURES = defaultdict(list)
_FAILURE_LOCK = threading.Lock()


def private_enabled():
    return os.getenv("SITE_PRIVATE_MODE", "0").strip() == "1"


def _password():
    return (os.getenv("SITE_ACCESS_PASSWORD") or os.getenv("AI_TEST_TOKEN") or "").strip()


def _serializer():
    password = _password()
    if len(password) < 16:
        return None
    return URLSafeTimedSerializer(password, salt="gaemi-gtp-dev-preview-v1")


def _authorized():
    signer = _serializer()
    if signer is None:
        return False
    cookie = request.cookies.get(COOKIE_NAME, "")
    if not cookie:
        return False
    try:
        return signer.loads(cookie, max_age=SESSION_TTL_SECONDS) == "dev"
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return False


def _attempt_allowed():
    # Only failed logins are limited. This is per worker, appropriate for
    # the private single-admin preview; production needs shared rate limits.
    remote = request.remote_addr or "unknown"
    now = time.monotonic()
    with _FAILURE_LOCK:
        attempts = [stamp for stamp in _FAILURES[remote] if now - stamp < FAILURE_WINDOW_SECONDS]
        _FAILURES[remote] = attempts
        return len(attempts) < MAX_FAILURES_PER_WINDOW


def _record_failure():
    remote = request.remote_addr or "unknown"
    with _FAILURE_LOCK:
        _FAILURES[remote].append(time.monotonic())


def _no_store(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def install_private_access(app, frontend_dir):
    @app.before_request
    def protect_preview():
        if not private_enabled():
            return None
        # CORS preflight carries no credentials; the actual request is checked.
        if request.method == "OPTIONS":
            return None
        if request.path == "/health" or request.path.startswith("/dev-access/"):
            return None
        # The relay route authenticates each request with its own Ed25519 signature.
        # Do not require browser preview cookies for the dedicated DO sender.
        if request.method == "POST" and request.path == "/internal/market/us-price-push":
            return None
        # The news worker may read only the two existing ranking GET routes.
        # This is not a login session and never grants access to other paths.
        if (request.method == "GET"
                and request.path in ("/market/trading-value", "/market/popular")):
            shared_token = os.getenv("NEWS_WORKER_RANKING_TOKEN", "").strip()
            supplied_token = request.headers.get("X-Gaemi-News-Worker-Token", "")
            if (len(shared_token) >= 32 and len(supplied_token) <= 512
                    and hmac.compare_digest(supplied_token, shared_token)):
                return None
        if _authorized():
            return None
        if request.path in {"/", "/index.html"}:
            return _no_store(send_from_directory(frontend_dir, "private-login.html"))
        if request.path.startswith(("/api/", "/debug/", "/disclosures/")) or request.path in {"/analyze", "/calendar", "/market/us-daily-chart"}:
            return _no_store(jsonify({"ok": False, "error": "private_access_required"})), 401
        return redirect("/", code=302)

    @app.after_request
    def prevent_private_caching(response):
        if private_enabled() and request.path != "/health":
            return _no_store(response)
        return response

    @app.get("/dev-access/status")
    def status():
        return jsonify({
            "private": private_enabled(),
            "authenticated": not private_enabled() or _authorized(),
        })

    @app.post("/dev-access/login")
    def login():
        if not private_enabled():
            return jsonify({"ok": True, "private": False})
        password = _password()
        signer = _serializer()
        if signer is None:
            return jsonify({"ok": False, "error": "site_password_not_configured"}), 503
        if not _attempt_allowed():
            return jsonify({"ok": False, "error": "too_many_attempts"}), 429
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "invalid_request"}), 400
        received = body.get("password")
        if not isinstance(received, str) or len(received) > 4096 or not hmac.compare_digest(received, password):
            _record_failure()
            return jsonify({"ok": False, "error": "invalid_password"}), 403
        token = signer.dumps("dev")
        response = jsonify({"ok": True, "private": True})
        response.set_cookie(
            COOKIE_NAME, token,
            max_age=SESSION_TTL_SECONDS,
            httponly=True, secure=True, samesite="Lax", path="/",
        )
        return response

    @app.post("/dev-access/logout")
    def logout():
        response = jsonify({"ok": True})
        response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True, samesite="Lax")
        return response
