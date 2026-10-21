"""One isolated Groq GPT-OSS 120B comparison: question-only system prompt.
Uses the already published 2026-10-20 US-close indices and the exact three
publisher article URLs (re-read live from the publishers); no DB writes.
Do not change production prompt, worker, app, or service.
"""
import json
import os
import sys
import urllib.request
import urllib.error
sys.path.insert(0, "/opt/gaemigtp-news/app")
import psycopg
from backend.services.news_detail import read_selected_article_details

QUESTION = "미국장은 어땠어?\n\n제목은 핵심만 짧게, 내용은 쉽고 구체적으로,\n해시태그는 최대 3개 반말로 답변해."
SESSION = "2026-10-20"
DB_URL = os.environ.get("NEWS_DATABASE_URL", "").strip()
KEY = os.environ.get("GROQ_API_KEY", "").strip()
if not DB_URL:
    raise SystemExit("TEST_STOP=missing_readonly_db_config")
if not KEY:
    raise SystemExit("TEST_STOP=missing_groq_api_key")
with psycopg.connect(DB_URL,connect_timeout=5) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT content,source_manifest FROM public.us_market_close_briefs WHERE session_date=%s AND status='published'",(SESSION,))
        row=cur.fetchone()
if not row:
    raise SystemExit("TEST_STOP=no_published_reference")
raw, manifest=row
stored=json.loads(raw) if isinstance(raw,str) else raw
if isinstance(manifest,str):
    manifest=json.loads(manifest)
if not isinstance(manifest,list) or len(manifest)!=3 or not isinstance(stored,dict):
    raise SystemExit("TEST_STOP=reference_shape")
idx=stored.get("market_indices")
if not isinstance(idx,list) or len(idx)!=3:
    raise SystemExit("TEST_STOP=indices_missing")
print("TEST_REFERENCE_SESSION="+SESSION,flush=True)
print("TEST_REFERENCE_ISSUES="+str(len(stored.get("issues") or [])),flush=True)
originals=read_selected_article_details(manifest,limit=3,with_sources=True)
articles=[]
for k,(ref,info) in enumerate(zip(manifest,originals),1):
    body=str(info.get("text") or "").strip()
    source=str(info.get("source") or "")
    print("TEST_ARTICLE_"+str(k)+"="+json.dumps({"title":ref.get("title"),"body_chars":len(body),"source":source},ensure_ascii=False),flush=True)
    if len(body)<700 or source not in ("article_or_main_paragraphs","jsonld_article_body"):
        raise SystemExit("TEST_STOP=article_body_unavailable_"+str(k))
    articles.append({"source_id":k,"title":ref["title"],"description":body[:5000]})
input_json=json.dumps({"session_date_et":SESSION,"market_indices":idx,"news":articles},ensure_ascii=False)
print("TEST_PROMPT="+QUESTION,flush=True)
print("TEST_INPUT_JSON_CHARS="+str(len(input_json)),flush=True)
payload={"model":"openai/gpt-oss-120b",
         "messages":[{"role":"system","content":QUESTION},
                     {"role":"user","content":input_json}],
         "temperature":0.2,"max_completion_tokens":1800,
         "reasoning_effort":"low","stream":False}
req=urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
    data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
    headers={"Authorization":"Bearer "+KEY,"Content-Type":"application/json",
             "User-Agent":"gaemiGTP-question-only-US-close-isolated/1.0"},
    method="POST")
print("TEST_ONE_API_CALL_START",flush=True)
try:
    with urllib.request.urlopen(req,timeout=48) as resp:
        result=json.load(resp)
except urllib.error.HTTPError as ex:
    print("TEST_API_ERROR=http_"+str(ex.code),flush=True)
    raise SystemExit(2)
except (urllib.error.URLError,TimeoutError,OSError,ValueError) as ex:
    print("TEST_API_ERROR="+type(ex).__name__,flush=True)
    raise SystemExit(3)
choices=result.get("choices") or []
msg=(choices[0].get("message") or {}) if choices else {}
answer=str(msg.get("content") or "").strip()
print("TEST_FINISH_REASON="+str(choices[0].get("finish_reason") if choices else "no_choices"),flush=True)
usage=result.get("usage") or {}
print("TEST_USAGE="+json.dumps({x:usage.get(x) for x in ("prompt_tokens","completion_tokens","total_tokens")}),flush=True)
print("TEST_ANSWER_BEGIN",flush=True)
print(answer[:6500],flush=True)
print("TEST_ANSWER_END",flush=True)
print("TEST_COMPLETE",flush=True)
