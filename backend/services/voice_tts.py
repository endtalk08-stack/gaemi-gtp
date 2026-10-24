"""Generate Korean speech in the user's supplied gaemiGTP voice using Fish Audio.

No background GPU server. Opt-in with FISH_API_KEY + GAEMI_VOICE_TTS_ENABLED=1.
The reference MP3 is reused from the already-shipped gaemi-voice-assets.js.
Never transmit credentials or source reference audio to the browser in this API.
"""
import base64
from collections import OrderedDict, defaultdict, deque
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request

import msgpack
from flask import Blueprint, jsonify, make_response, request

voice_tts_bp = Blueprint("gaemi_voice_tts", __name__)
_API_URL = "https://api.fish.audio/v1/tts"
_REFERENCE_TRANSCRIPT = "개미 여러분, 오늘도 돈 되는 이슈만 쏙쏙 골라왔습니다. 바로 시작하시죠."
_REFERENCE_JS = Path(__file__).resolve().parents[2] / "frontend" / "js" / "gaemi-voice-assets.js"
_SAMPLE_PATTERN = re.compile(r"\bsample\s*:\s*asBlobUrl\(\s*'([A-Za-z0-9+/=]+)'\s*,\s*'audio/mpeg'\s*\)")
_MAX_TEXT_CHARS = 1500
_MAX_REQUEST_BYTES = 6000
_MAX_AUDIO_BYTES = 6 * 1024 * 1024
_CACHE_TTL_SECONDS = 6 * 3600
_CACHE_ENTRIES = 32
_MAX_PER_DAY = 40  # per worker process, not an account-wide budget
_CLIENT_PER_10_MINUTES = 8
_MAX_CONCURRENT = 2
_lock = threading.RLock()
_slots = threading.BoundedSemaphore(_MAX_CONCURRENT)
_cache = OrderedDict()
_clients = defaultdict(deque)
_calls_day = None
_calls_count = 0
_reference_audio = None


def _configured():
    return (os.environ.get("GAEMI_VOICE_TTS_ENABLED", "").lower() in ("1", "true", "yes")
            and bool(os.environ.get("FISH_API_KEY", "").strip()))


def _sample_audio():
    global _reference_audio
    if _reference_audio is not None:
        return _reference_audio
    source = _REFERENCE_JS.read_text(encoding="utf-8")
    found = _SAMPLE_PATTERN.search(source)
    if not found:
        raise RuntimeError("reference_audio_missing")
    data = base64.b64decode(found.group(1), validate=True)
    if not (1000 <= len(data) <= 1_000_000) or not (data.startswith(b"ID3") or data.startswith(b"\xff\xfb")):
        raise RuntimeError("reference_audio_invalid")
    _reference_audio = data
    return data


def _cache_key(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_cache(key):
    with _lock:
        item = _cache.get(key)
        if item and item[0] > time.monotonic():
            _cache.move_to_end(key)
            return item[1]
        _cache.pop(key, None)
    return None


def _put_cache(key, audio):
    with _lock:
        _cache[key] = (time.monotonic() + _CACHE_TTL_SECONDS, audio)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_ENTRIES:
            _cache.popitem(last=False)


def _request_permitted():
    global _calls_day, _calls_count
    now = time.monotonic()
    day = datetime.now(timezone.utc).date()
    client = request.remote_addr or "unknown"
    with _lock:
        if _calls_day != day:
            _calls_day = day
            _calls_count = 0
            _clients.clear()
        times = _clients[client]
        while times and times[0] < now - 600:
            times.popleft()
        if len(times) >= _CLIENT_PER_10_MINUTES or _calls_count >= _MAX_PER_DAY:
            return False
        times.append(now)
        _calls_count += 1
        return True


def _fish_synthesize(text):
    payload = msgpack.packb({
        "text": text,
        "references": [{"audio": _sample_audio(), "text": _REFERENCE_TRANSCRIPT}],
        "format": "mp3", "latency": "normal"
    }, use_bin_type=True)
    req = urllib.request.Request(_API_URL, data=payload, method="POST", headers={
        "Authorization": "Bearer " + os.environ["FISH_API_KEY"],
        "Content-Type": "application/msgpack", "model": "s2.1-pro", "Accept": "audio/mpeg"
    })
    with urllib.request.urlopen(req, timeout=35) as resp:
        media_type = resp.headers.get("Content-Type", "").lower()
        if media_type and not ("audio/" in media_type or "octet-stream" in media_type):
            raise RuntimeError("tts_invalid_response_content_type")
        audio = resp.read(_MAX_AUDIO_BYTES + 1)
    if not 200 <= len(audio) <= _MAX_AUDIO_BYTES:
        raise RuntimeError("tts_audio_size_invalid")
    return audio


@voice_tts_bp.get("/api/voice/status")
def gaemi_voice_status():
    result = jsonify({"ok": True, "available": _configured()})
    result.headers["Cache-Control"] = "no-store"
    return result


@voice_tts_bp.post("/api/voice/tts")
def gaemi_voice_tts():
    if not _configured():
        return jsonify({"ok": False, "error": "voice_unavailable"}), 503
    if request.content_length is None or request.content_length > _MAX_REQUEST_BYTES:
        return jsonify({"ok": False, "error": "invalid_request_size"}), 413
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
        return jsonify({"ok": False, "error": "invalid_text"}), 400
    speech_text = " ".join(payload["text"].split())
    if not speech_text or len(speech_text) > _MAX_TEXT_CHARS or "<|" in speech_text:
        return jsonify({"ok": False, "error": "invalid_text"}), 400
    key = _cache_key(speech_text)
    audio = _read_cache(key)
    hit = audio is not None
    if not hit:
        if not _request_permitted():
            return jsonify({"ok": False, "error": "voice_rate_limited"}), 429
        if not _slots.acquire(blocking=False):
            return jsonify({"ok": False, "error": "voice_busy"}), 503
        try:
            audio = _fish_synthesize(speech_text)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError, OSError, ValueError) as exc:
            print("[voice tts] failed: " + type(exc).__name__, flush=True)
            return jsonify({"ok": False, "error": "voice_generation_failed"}), 502
        finally:
            _slots.release()
        _put_cache(key, audio)
    output = make_response(audio)
    output.headers["Content-Type"] = "audio/mpeg"
    output.headers["Cache-Control"] = "private, no-store"
    output.headers["X-Gaemi-Voice-Cache"] = "hit" if hit else "miss"
    return output
