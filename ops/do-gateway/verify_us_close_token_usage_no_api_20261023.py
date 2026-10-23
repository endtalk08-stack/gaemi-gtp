"""Read-only no-network check for original model-2 US-close Groq token recording."""
import datetime as dt
import json
import os
from unittest.mock import patch
from backend.services import us_market_close as close

assert close.MODEL == "openai/gpt-oss-120b"
assert close.US_CLOSE_PROMPT == "쉽게 설명 반말로 대답해"
assert close.US_CLOSE_QUESTION == "미국장은 어땠어?"
assert close.FREE_TEXT_FORMAT == "free_text_v1"
assert "len(articles) != 2" in __import__("inspect").getsource(close.publish_once)
sample_text = "미국장 상승 및 하락 원인, 기술주 실적과 지수 동향을 분석한 참고 기사 본문입니다. " * 12
articles = [
    {"title": "시장 마감", "description": sample_text},
    {"title": "주식 동향", "description": sample_text + "추가 의견"},
]
indices = [
    {"name": "다우존스", "session_date_et": "2026-10-22", "close": 52867.98, "change_pct": 0.02},
    {"name": "나스닥 종합", "session_date_et": "2026-10-22", "close": 26008.86, "change_pct": -2.6},
    {"name": "S&P 500", "session_date_et": "2026-10-22", "close": 7663.43, "change_pct": -1.21},
]
class FakeResp:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self):
        return json.dumps({
            "choices": [{"message": {"content": "어제 미국 증시는 기술주 급락과 실적 우려가 겹치면서 나스닥이 크게 밀렸어. 다우는 상대적으로 안정적이었고, 반도체와 AI 관련 주식은 투자자들의 매도 압력을 받았어. 다만 이 내용은 테스트용 가짜 답변이야."}}],
            "usage": {"prompt_tokens": 2400, "completion_tokens": 320, "total_tokens": 2720},
        }).encode()
def fake_urlopen(request, timeout=None):
    payload = json.loads(request.data)
    assert payload["model"] == close.MODEL
    assert payload["messages"][0]["content"] == close.US_CLOSE_PROMPT
    assert payload["messages"][1]["content"].endswith("질문: " + close.US_CLOSE_QUESTION)
    assert sample_text in payload["messages"][1]["content"]
    assert payload["max_completion_tokens"] == 1500
    assert payload["reasoning_effort"] == "low"
    assert "response_format" not in payload
    return FakeResp()
usage = {}
with patch.dict(os.environ, {"GROQ_API_KEY": "fake-no-network-test-key"}), patch.object(close.urllib.request, "urlopen", fake_urlopen):
    answer = close._generate(articles, dt.date(2026, 10, 22), indices=indices, usage_out=usage)
assert len(answer) >= 100
assert usage == {"prompt_tokens": 2400, "completion_tokens": 320, "total_tokens": 2720}
document = {
    "session_date_et": "2026-10-22", "market_indices": indices, "response_format": close.FREE_TEXT_FORMAT,
    "issues": [{"headline": "미국장 마감", "summary": answer, "tags": [], "source_ids": []}],
}
before = close._display_brief_content(json.dumps(document, ensure_ascii=False))
document["usage"] = usage
after = close._display_brief_content(json.dumps(document, ensure_ascii=False))
present = close._structured_brief(json.dumps(document, ensure_ascii=False))
assert before == after
assert present["usage"] == usage and present["response_format"] == close.FREE_TEXT_FORMAT
print("US_CLOSE_TOKEN_METER_TEST=PASS no_real_ai_call=true original_prompt_unchanged=true two_articles=true log_and_presentation=true", flush=True)
