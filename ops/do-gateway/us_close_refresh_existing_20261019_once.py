"""One-time controlled update of OLD 2026-10-19 US-close brief only.

Requires the existing published/legacy Neon row, verifies its old content and
the session/date-locked actual Naver indices and 3 original publisher articles.
Runs approved exact prompt through Groq ONE time; compare-and-swap DB update
only when the original row remains unchanged. No new timers/jobs/services.
Never stores original publisher article bodies or secrets.
"""
import datetime as dt
import hashlib
import json
import re
import sys
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services import us_market_close as app
from backend.services.us_market_close_runtime import verified_indices
DAY=dt.date(2026,10,19)

def seal(content):
    return hashlib.sha256(str(content).encode()).hexdigest()[:16]

def main():
    print("US_CLOSE_REFRESH_SCOPE=ONLY_2026-10-19_old_published_row_one_Groq_call_CAS",flush=True)
    # Preflight row before any provider calls; no repeat AI if already updated.
    with app._connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT status,content,model,jsonb_array_length(source_manifest),
                expires_at>now() FROM public.us_market_close_briefs WHERE session_date=%s""",(DAY,))
            row=cur.fetchone()
    if not row:
        print("US_CLOSE_REFRESH_BLOCKED=not_published_record",flush=True);return 2
    status,old,model,count,alive=row
    try: previous=json.loads(old or "")
    except Exception:previous={}
    if isinstance(previous,dict) and previous.get("market_indices"):
        print("US_CLOSE_REFRESH_ALREADY_NEW_FORMAT",flush=True);return 0
    if status!="published" or not old or not alive or model!="openai/gpt-oss-120b" or count!=10:
        print("US_CLOSE_REFRESH_BLOCKED=legacy_row_metadata_mismatch",flush=True)
        return 3
    if len(old)<100 or len(old)>1300:
        print("US_CLOSE_REFRESH_BLOCKED=legacy_content_length_mismatch",flush=True)
        return 4
    print("US_CLOSE_REFRESH_OLD="+json.dumps({"session":str(DAY),"status":status,
        "length":len(old),"source_manifest_count":count,"sha16":seal(old)},ensure_ascii=False),flush=True)
    try:
        indices=verified_indices(DAY)
        articles=app.collect_articles(DAY)
        if len(indices)!=3 or len(articles)!=3:
            raise ValueError("insufficient_data")
        for item in articles:
            if len(item.get("description") or "")<700:raise ValueError("short_body")
        print("US_CLOSE_REFRESH_INPUT="+json.dumps({
            "indices":[{"code":i["symbol"],"close":i["close"],"change_pct":i["change_pct"],
                        "date":i["session_date_et"]} for i in indices],
            "verified_originals":len(articles),
            "original_lengths":[len(a["description"]) for a in articles]},ensure_ascii=False),flush=True)
    except Exception as exc:
        print("US_CLOSE_REFRESH_BLOCKED=source_validation_"+type(exc).__name__,flush=True);return 5
    print("US_CLOSE_REFRESH_AI_CALL_MAX=1",flush=True)
    try:
        raw=app._generate(articles,DAY,indices=indices)
        parsed=json.loads(raw)
        if not isinstance(parsed,dict) or not isinstance(parsed.get("issues"),list) or not parsed["issues"]:
            raise ValueError("invalid_ai_shape")
        accepted=[]
        for issue in parsed["issues"][:3]:
            if not isinstance(issue,dict):continue
            title=str(issue.get("headline") or "").strip()
            summary=str(issue.get("summary") or "").strip()
            if not title or not summary or re.search(r"코스피|코스닥|국내증시",title+summary):
                continue
            ids=[v for v in (issue.get("source_ids") or []) if isinstance(v,int) and 1<=v<=3]
            accepted.append({"headline":title[:200],"summary":summary[:2600],
                "tags":[str(v)[:48] for v in (issue.get("tags") or [])[:3]],
                "source_ids":ids})
        if not accepted:raise ValueError("no_usable_AI")
        envelope={"session_date_et":DAY.isoformat(),"market_indices":indices,"issues":accepted}
        document=json.dumps(envelope,ensure_ascii=False)
        rendered=app._display_brief_content(document)
        required=("2026-10-19","51,966.03","26,430.89","7,690.73")
        if not all(marker in rendered for marker in required):raise ValueError("render_validation_failed")
        manifest=[{k:item[k] for k in ("title","url","published_at","publisher")} for item in articles]
        print("US_CLOSE_REFRESH_AI_VALID="+json.dumps({"issues":len(accepted),
                "render_chars":len(rendered),"document_chars":len(document),
                "model":"openai/gpt-oss-120b","author_prompt_unchanged":True},ensure_ascii=False),flush=True)
    except Exception as exc:
        print("US_CLOSE_REFRESH_BLOCKED=AI_validation_"+type(exc).__name__,flush=True);return 6
    # Atomic compare-and-swap only on the exact old content, with row lock held
    # solely during the single UPDATE; if changed concurrently, do not replace.
    with app._connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE public.us_market_close_briefs SET
               content=%s,source_manifest=%s::jsonb,published_at=now(),
               expires_at=now()+interval '24 hours'
               WHERE session_date=%s AND status='published' AND content=%s
               AND expires_at>now() RETURNING session_date""",
               (document,json.dumps(manifest,ensure_ascii=False),DAY,old))
            updated=cur.fetchone()
    if not updated:
        print("US_CLOSE_REFRESH_BLOCKED=row_changed_since_preflight",flush=True);return 7
    print("US_CLOSE_REFRESH_PUBLISHED="+DAY.isoformat(),flush=True)
    print("US_CLOSE_REFRESH_NEW_SHA16="+seal(document),flush=True)
    print("US_CLOSE_REFRESH_SUCCESS",flush=True)
    return 0
if __name__=="__main__":sys.exit(main())
