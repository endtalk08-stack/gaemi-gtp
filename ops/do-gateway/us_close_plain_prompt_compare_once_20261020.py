"""One-off US close plain-prompt comparison; no database operations."""
import datetime as dt
import json
import os
import urllib.request
import sys
sys.path.insert(0, '/opt/gaemigtp-news/app')
from backend.services.us_market_close_runtime import verified_originals

session = dt.date(2026, 10, 19)
articles = verified_originals(session)
print("TEST_ARTICLE_COUNT=" + str(len(articles)), flush=True)
for i, a in enumerate(articles, 1):
    print(f"TEST_SOURCE_{i}_CHARS={a['body_chars']} PUBLISHER={a['publisher']}", flush=True)
if len(articles) != 3:
    raise SystemExit("STOP_NO_THREE_VERIFIED_ARTICLES_NO_AI_CALL")
prompt = """제공된 기사를 근거로 미국장은 어땠어? 를 작성해
제목은 핵심만 짧게, 내용은 쉽고 구체적으로, 해시태그는 최대 3개. 반말로 답변해."""
news = "\n\n".join(f"[기사 {i}]\n제목: {a['title']}\n본문: {a['description']}" for i, a in enumerate(articles, 1))
key = os.environ.get("GROQ_API_KEY", "").strip()
if not key:
    raise SystemExit("STOP_GROQ_KEY_UNAVAILABLE")
payload = {
    "model": "openai/gpt-oss-120b",
    "messages": [
        {"role": "system", "content": prompt},
        {"role": "user", "content": news},
    ],
    "temperature": 0.2,
    "max_completion_tokens": 1800,
    "reasoning_effort": "low",
    "stream": False,
}
req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
             "User-Agent": "gaemiGTP-us-close-one-off-plain-test/1.0"}, method="POST")
print("TEST_AI_CALL_START=one_plain_prompt_call_no_db", flush=True)
with urllib.request.urlopen(req, timeout=65) as resp:
    data = json.load(resp)
choice = (data.get("choices") or [{}])[0]
content = (choice.get("message") or {}).get("content") or ""
print("TEST_FINISH_REASON=" + str(choice.get("finish_reason")), flush=True)
print("TEST_USAGE=" + json.dumps(data.get("usage") or {}, ensure_ascii=False), flush=True)
print("TEST_OUTPUT_CHARS=" + str(len(content)), flush=True)
print("TEST_OUTPUT_BEGIN", flush=True)
print(content[:6500], flush=True)
print("TEST_OUTPUT_END", flush=True)
