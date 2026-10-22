"""One-time targeted repair for failed US-close 2026-10-22, never retry a published/processing result."""
import os,sys,datetime as dt,json,re
sys.path.insert(0,os.getcwd())
from backend.services import us_market_close as close

TARGET=dt.date(2026,10,22)
with close._connection() as conn:
 with conn.cursor() as cur:
  cur.execute("SELECT status, jsonb_array_length(coalesce(source_manifest,'[]'::jsonb)) FROM public.us_market_close_briefs WHERE session_date=%s",(TARGET,))
  row=cur.fetchone()
print("TARGET_STATE_BEFORE",row,flush=True)
if not row or row[0]!="failed" or row[1]!=3:
 print("REPAIR_SKIPPED not exactly failed with three manifest sources",flush=True)
 sys.exit(0)

now=dt.datetime.now(dt.timezone.utc)
if now.astimezone(close.NY).date()!=TARGET or now.astimezone(close.NY).hour<16:
 print("REPAIR_SKIPPED outside original trading session date",flush=True)
 sys.exit(0)

indices=close.verified_indices(TARGET)
print("INDICES_VERIFIED",[(x.get("name"),x.get("session_date_et")) for x in indices],flush=True)
if len(indices)!=3 or any(x.get("session_date_et")!=TARGET.isoformat() for x in indices):
 print("REPAIR_SKIPPED bad indices",flush=True)
 sys.exit(0)
articles=close.collect_articles(TARGET,now_utc=now)
print("ARTICLE_COUNT",len(articles),"PUBLISHERS",[x.get("publisher") for x in articles],flush=True)
if len(articles)!=3:
 print("REPAIR_SKIPPED insufficient originals, no AI call",flush=True)
 sys.exit(0)

# Only one job can reserve this failed row. Leave prior source manifest intact until success.
with close._connection() as conn:
 with conn.cursor() as cur:
  cur.execute("UPDATE public.us_market_close_briefs SET status='processing' WHERE session_date=%s AND status='failed' RETURNING session_date",(TARGET,))
  claimed=cur.fetchone() is not None
print("REPAIR_CLAIMED",claimed,flush=True)
if not claimed:sys.exit(0)

try:
 # Keep all three fully verified source articles, but cap text fed to the 8K TPM 120B model.
 compact=[{**item,"description":str(item.get("description") or "")[:1300]} for item in articles]
 print("AI_SOURCE_INPUT_CHARS",sum(len(item["description"]) for item in compact),flush=True)
 # Same approved 120B model + system prompt, with JSON mode to prevent non-JSON replies.
 import urllib.request,urllib.error
 request_data={"model":close.MODEL,
  "messages":[{"role":"system","content":close.US_CLOSE_PROMPT},
              {"role":"user","content":close._prompt(compact,TARGET,indices=indices)}],
  "temperature":0.2,"max_completion_tokens":1800,"reasoning_effort":"low",
  "stream":False,"response_format":{"type":"json_object"}}
 request=urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
  data=json.dumps(request_data,ensure_ascii=False).encode("utf-8"),
  headers={"Authorization":"Bearer "+os.environ["GROQ_API_KEY"].strip(),"Content-Type":"application/json","User-Agent":"gaemiGTP-us-close/1.0"},method="POST")
 try:
  with urllib.request.urlopen(request,timeout=35) as response:
   api_result=json.loads(response.read().decode("utf-8"))
 except urllib.error.HTTPError as e:
  msg=e.read(600).decode("utf-8","replace")
  msg=re.sub(r"org_[A-Za-z0-9_-]+","org_[REDACTED]",msg)
  print("GROQ_HTTP_ERROR",e.code,"BODY",msg[:420],flush=True)
  raise
 choices=api_result.get("choices") or []
 answer=str(((choices[0].get("message") or {}).get("content")) or "").strip() if choices else ""
 print("GROQ_RESPONSE","LENGTH",len(answer),"FINISH",choices[0].get("finish_reason") if choices else "none",flush=True)
 result=json.loads(answer)
 if not isinstance(result,dict) or not isinstance(result.get("issues"),list) or not result["issues"]:
  raise RuntimeError("us_close_ai_missing_issues")
 issues=[]
 for item in result["issues"][:3]:
  if not isinstance(item,dict):continue
  head=str(item.get("headline") or "").strip()
  summ=str(item.get("summary") or "").strip()
  if not head or not summ or re.search(r"코스피|코스닥|국내증시",head+summ):continue
  sources=[i for i in (item.get("source_ids") or []) if type(i)==int and 1<=i<=3]
  issues.append({"headline":head[:200],"summary":summ[:2600],"tags":[str(t)[:48] for t in (item.get("tags") or [])[:3]],"source_ids":sources})
 if not issues:raise RuntimeError("no_usable_us_issues")
 payload=json.dumps({"session_date_et":TARGET.isoformat(),"market_indices":indices,"issues":issues},ensure_ascii=False)
 if close._structured_brief(payload) is None:
  raise RuntimeError("result_validation_failed")
 manifest=json.dumps([{k:a[k] for k in ("title","url","published_at","publisher")} for a in articles],ensure_ascii=False)
 with close._connection() as conn:
  with conn.cursor() as cur:
   cur.execute("""UPDATE public.us_market_close_briefs SET status='published',content=%s,published_at=now(),expires_at=now()+interval '24 hours',source_manifest=%s::jsonb WHERE session_date=%s AND status='processing' RETURNING session_date""",(payload,manifest,TARGET))
   saved=cur.fetchone() is not None
 print("REPAIR_PUBLISHED",saved,"ISSUES",len(issues),"JSON_CHARS",len(payload),flush=True)
 if not saved:raise RuntimeError("published_update_failed")
except Exception as exc:
 with close._connection() as conn:
  with conn.cursor() as cur:
   cur.execute("UPDATE public.us_market_close_briefs SET status='failed' WHERE session_date=%s AND status='processing'",(TARGET,))
 print("REPAIR_ERROR",type(exc).__name__,str(exc)[:260],flush=True)
 raise
