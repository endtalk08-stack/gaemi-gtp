"""Regenerate October 22 US close exactly in the original model-2 free-answer format, using two originals.
No change to any AI system prompt, model settings, question or original-body extraction.
Only update already-published 2026-10-22 brief after a successful and validated AI reply.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
sys.path.insert(0, os.getcwd())
from backend.services import us_market_close as close
from backend.services import us_market_close_runtime as runtime

TARGET = dt.date(2026, 10, 22)
with close._connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""SELECT status, content, model FROM public.us_market_close_briefs
                       WHERE session_date=%s""", (TARGET,))
        prior = cur.fetchone()
if prior is None or prior[0] != "published" or prior[2] != close.MODEL:
    print("REGEN_SKIPPED invalid previous publication", flush=True)
    sys.exit(0)
try:
    previous = json.loads(prior[1])
except (TypeError, ValueError):
    print("REGEN_SKIPPED unknown existing content", flush=True)
    sys.exit(0)
if previous.get("response_format") == close.FREE_TEXT_FORMAT:
    print("REGEN_SKIPPED already original model2 free-text", flush=True)
    sys.exit(0)
assert close.MODEL == "openai/gpt-oss-120b"
assert close.US_CLOSE_PROMPT == "쉽게 설명 반말로 대답해"
assert close.US_CLOSE_QUESTION == "미국장은 어땠어?"
assert close.FREE_TEXT_FORMAT == "free_text_v1"

now = dt.datetime.now(dt.timezone.utc)
indices = close.verified_indices(TARGET)
if len(indices) != 3 or any(x["session_date_et"] != TARGET.isoformat() for x in indices):
    raise RuntimeError("target index date mismatch")
articles = close.collect_articles(TARGET, now_utc=now)
if len(articles) != 2:
    raise RuntimeError("expected exactly two verified originals")
print("MODEL_2_ORIGINAL_PROMPT_VERIFIED=True", flush=True)
print("SOURCE_COUNT=2", "ARTICLE_INPUT_CHARS", [len(x["description"]) for x in articles],
      "PUBLISHERS", [x["publisher"] for x in articles], flush=True)
original_request = close._prompt(articles, TARGET, indices=indices)
print("PROMPT_DATA_UTF8_BYTES", len(original_request.encode("utf-8")), flush=True)
try:
    answer = close._generate(articles, TARGET, indices=indices)
except urllib.error.HTTPError as exc:
    try:
        body = exc.read(450).decode("utf-8", "replace")
    except Exception:
        body = ""
    print("GROQ_ERROR", exc.code, "BODY", body[:350], flush=True)
    raise
if not isinstance(answer, str) or len(answer.strip()) < 100 or re.search(r"코스피|코스닥|국내증시", answer):
    raise RuntimeError("invalid_model2_free_text")
issues = [{
    "headline": "미국장 마감",
    "summary": answer.strip()[:3600],
    "tags": close._code_chart_tags(answer, indices),
    "source_ids": [],
}]
payload = json.dumps({
    "session_date_et": TARGET.isoformat(),
    "market_indices": indices,
    "response_format": close.FREE_TEXT_FORMAT,
    "issues": issues,
}, ensure_ascii=False)
if close._structured_brief(payload) is None:
    raise RuntimeError("free_text_presentation_invalid")
manifest = json.dumps([
    {key: item[key] for key in ("title", "url", "published_at", "publisher")}
    for item in articles
], ensure_ascii=False)
with close._connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE public.us_market_close_briefs
            SET content=%s, status='published', source_manifest=%s::jsonb,
                published_at=now(), expires_at=now()+interval '24 hours'
            WHERE session_date=%s AND status='published'
              AND (content::jsonb->>'response_format') IS DISTINCT FROM %s
            RETURNING session_date
        """, (payload, manifest, TARGET, close.FREE_TEXT_FORMAT))
        applied = cur.fetchone() is not None
if not applied:
    raise RuntimeError("concurrent_regeneration_protected")
print("REGEN_PUBLISHED", applied, "SESSION", TARGET.isoformat(), "ARTICLES", len(articles),
      "FORMAT", close.FREE_TEXT_FORMAT, "ANSWER_CHARS", len(answer),
      "CONTENT_SHA256", hashlib.sha256(payload.encode()).hexdigest()[:16], flush=True)
print("ANSWER_BEGIN", answer[:1800].replace("\n", " "), flush=True)
check = close.read_brief()
print("NEON_VISIBLE", bool(check), "SESSION", check.get("session_date") if check else None,
      "FORMAT", (check.get("presentation") or {}).get("response_format") if check else None, flush=True)
