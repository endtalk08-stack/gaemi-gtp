"""Offline tests: no paid Fish API requests are issued."""
import os
import unittest
from unittest.mock import patch
from flask import Flask
from backend.services import voice_tts


class VoiceTTSTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(voice_tts.voice_tts_bp)
        self.client = app.test_client()
        with voice_tts._lock:
            voice_tts._cache.clear()
            voice_tts._clients.clear()
            voice_tts._calls_day = None
            voice_tts._calls_count = 0

    def test_disabled_never_calls_provider(self):
        with patch.dict(os.environ, {"GAEMI_VOICE_TTS_ENABLED": "0", "FISH_API_KEY": "dummy"}), \
             patch.object(voice_tts.urllib.request, "urlopen", side_effect=AssertionError("paid API called")):
            self.assertFalse(self.client.get("/api/voice/status").json["available"])
            result = self.client.post("/api/voice/tts", json={"text": "안녕하세요"})
            self.assertEqual(result.status_code, 503)

    def test_korean_reference_and_cache(self):
        calls = []
        class FakeResponse:
            headers = {"Content-Type": "audio/mpeg"}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return b"ID3" + b"A" * 400
        def urlopen(req, timeout):
            calls.append(req)
            body = voice_tts.msgpack.unpackb(req.data, raw=False)
            self.assertEqual(body["text"], "삼성전자 상승")
            self.assertEqual(body["references"][0]["text"], voice_tts._REFERENCE_TRANSCRIPT)
            self.assertGreater(len(body["references"][0]["audio"]), 1000)
            self.assertEqual(req.get_header("Authorization"), "Bearer test")
            return FakeResponse()
        with patch.dict(os.environ, {"GAEMI_VOICE_TTS_ENABLED": "1", "FISH_API_KEY": "test"}), \
             patch.object(voice_tts.urllib.request, "urlopen", side_effect=urlopen):
            self.assertTrue(self.client.get("/api/voice/status").json["available"])
            result = self.client.post("/api/voice/tts", json={"text": "삼성전자 상승"})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.mimetype, "audio/mpeg")
            result = self.client.post("/api/voice/tts", json={"text": "삼성전자 상승"})
            self.assertEqual(result.headers["X-Gaemi-Voice-Cache"], "hit")
            self.assertEqual(len(calls), 1)

    def test_rejects_bad_text(self):
        with patch.dict(os.environ, {"GAEMI_VOICE_TTS_ENABLED": "1", "FISH_API_KEY": "test"}):
            self.assertEqual(self.client.post("/api/voice/tts", json={"text": "a" * 1501}).status_code, 400)
            self.assertEqual(self.client.post("/api/voice/tts", json={"text": "<|speaker:0|>hi"}).status_code, 400)
            self.assertEqual(self.client.post("/api/voice/tts", json={"text": 1}).status_code, 400)

    def test_daily_budget(self):
        with patch.dict(os.environ, {"GAEMI_VOICE_TTS_ENABLED": "1", "FISH_API_KEY": "test"}):
            voice_tts._calls_day = voice_tts.datetime.now(voice_tts.timezone.utc).date()
            voice_tts._calls_count = voice_tts._MAX_PER_DAY
            response = self.client.post("/api/voice/tts", json={"text": "unseen phrase"})
            self.assertEqual(response.status_code, 429)


if __name__ == "__main__":
    unittest.main()
