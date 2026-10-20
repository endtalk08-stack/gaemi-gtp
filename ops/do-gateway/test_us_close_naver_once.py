"""One-shot NAVER '뉴욕증시 마감' -> unchanged US_CLOSE_PROMPT -> one Groq 120B test.

Runs solely via existing DigitalOcean gateway run; no DB, files, main app,
service changes, new providers, schedules, or retries. Never logs secrets.
Source: main/backend/services/us_market_close.py current editorial prompt.
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
UTC = datetime.timezone.utc
PROMPT = """제공된 기사를 근거로 미국장은 어땠어? 를 작성해

제목은 핵심만 짧게, 내용은 쉽고 구체적으로, 해시태그는 최대 3개. 반말로 답변해.

한국어 JSON 객체만 반환해:
{"issues":[{"headline":"제목","summary":"기사에 근거한 내용","tags":["#핵심어"],"source_ids":[1]}]}"""
MODEL = "openai/gpt-oss-120b"
QUERY = "뉴욕증시 마감"

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))).strip()

def fetch_naver():
    client_id = os.getenv("NAVER_CLIENT_ID", "").strip()
    client_secret = os.getenv("NAVER_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("NAVER_CLOSE_TEST_ERROR=naver_credentials_not_in_worker_env", flush=True)
        return None
    path = "/search/v1/news?" + urllib.parse.urlencode({
        "query": QUERY, "display": 50, "start": 1, "sort": "date", "format": "json",
    })
    req = urllib.request.Request(
        "https://naverapihub.apigw.ntruss.com" + path,
        headers={
            "X-NCP-APIGW-API-KEY-ID": client_id,
            "X-NCP-APIGW-API-KEY": client_secret,
            "User-Agent": "gaemiGTP-us-close-once-test/1.0",
        },
        method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read(350000))
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            print("NAVER_CLOSE_TEST_ERROR=bad_provider_shape", flush=True)
            return None
        return data["items"][:50]
    except urllib.error.HTTPError as exc:
        print("NAVER_CLOSE_TEST_ERROR=naver_http_"+str(exc.code),flush=True)
    except Exception as exc:
        print("NAVER_CLOSE_TEST_ERROR=naver_"+type(exc).__name__,flush=True)
    return None

def select(rows, session_date):
    close=datetime.datetime.combine(session_date,datetime.time(16,0),tzinfo=NY)
    next_open=(close+datetime.timedelta(days=1)).replace(hour=9,minute=30)
    candidates=[]
    for row in rows:
        try:
            published=parsedate_to_datetime(str(row.get("pubDate") or "")).astimezone(NY)
        except (TypeError, ValueError, IndexError):
            continue
        if not (close<=published<next_open):
            continue
        title=clean(row.get("title"))
        description=clean(row.get("description"))
        url=str(row.get("originallink") or row.get("link") or "").strip()
        if not title or not description or not url:
            continue
        candidates.append((published, title, description, url))
    candidates.sort(key=lambda x:x[0],reverse=True)
    selected=[]
    seen_urls=set()
    seen_titles=set()
    for timestamp,title,description,url in candidates:
        if url in seen_urls or title in seen_titles:
            continue
        seen_urls.add(url);seen_titles.add(title)
        selected.append({
            "title":title,"description":description,
            "published_kst":timestamp.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
            "url":url,
        })
        if len(selected)>=10:break
    return selected

def generate(rows):
    key=os.getenv("GROQ_API_KEY","").strip()
    if not key:
        print("NAVER_CLOSE_TEST_ERROR=groq_credentials_not_in_worker_env",flush=True)
        return None
    prompt_news=[
        {"source_id":i+1,"title":x["title"],"description":x["description"]}
        for i,x in enumerate(rows)
    ]
    req=urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps({"model":MODEL,"messages":[
            {"role":"system","content":PROMPT},
            {"role":"user","content":json.dumps(prompt_news,ensure_ascii=False)}
        ],"temperature":0.2,"max_completion_tokens":1800,
        "reasoning_effort":"low","stream":False},
        ensure_ascii=False).encode("utf-8"),
        headers={"Authorization":"Bearer "+key,"Content-Type":"application/json",
                 "User-Agent":"gaemiGTP-us-close-once-test/1.0"},
        method="POST")
    print("NAVER_CLOSE_TEST_AI_CALL_MAX=1",flush=True)
    try:
        with urllib.request.urlopen(req,timeout=38) as resp:
            obj=json.loads(resp.read(160000))
        choice=(obj.get("choices") or [{}])[0]
        text=str((choice.get("message") or {}).get("content") or "").strip()
        usage=obj.get("usage") or {}
        if usage:
            print("NAVER_CLOSE_TEST_TOKENS="+json.dumps({
                "prompt_tokens":usage.get("prompt_tokens"),
                "completion_tokens":usage.get("completion_tokens"),
                "total_tokens":usage.get("total_tokens"),
            }),flush=True)
        print("NAVER_CLOSE_TEST_FINISH="+str(choice.get("finish_reason")),flush=True)
        try:
            parsed=json.loads(text)
            if not isinstance(parsed,dict) or not isinstance(parsed.get("issues"),list):
                print("NAVER_CLOSE_TEST_RESULT_NONSCHEMA="+text[:3200],flush=True)
                return False
            issues=[]
            for item in parsed.get("issues")[:5]:
                if not isinstance(item,dict):continue
                sources=[v for v in (item.get("source_ids") or []) if isinstance(v,int) and 1<=v<=len(rows)]
                issues.append({
                    "headline":str(item.get("headline") or "")[:180],
                    "summary":str(item.get("summary") or "")[:1100],
                    "tags":(item.get("tags") or [])[:3],
                    "source_ids":sources,
                })
            if not issues:
                print("NAVER_CLOSE_TEST_ERROR=empty_issues",flush=True)
                return False
            print("NAVER_CLOSE_TEST_RESULT="+json.dumps({"issues":issues},ensure_ascii=False),flush=True)
            print("NAVER_CLOSE_TEST_AI_VALID=true",flush=True)
            return True
        except (ValueError,TypeError):
            print("NAVER_CLOSE_TEST_RESULT_NONJSON="+text[:3200],flush=True)
            return False
    except urllib.error.HTTPError as exc:
        print("NAVER_CLOSE_TEST_ERROR=groq_http_"+str(exc.code),flush=True)
    except Exception as exc:
        print("NAVER_CLOSE_TEST_ERROR=groq_"+type(exc).__name__,flush=True)
    return False

def main():
    now=datetime.datetime.now(UTC)
    local=now.astimezone(NY)
    session_date=local.date() if (local.hour>=16 and local.weekday()<5) else (
        local-datetime.timedelta(days=1)).date()
    while session_date.weekday()>=5:
        session_date-=datetime.timedelta(days=1)
    print("NAVER_CLOSE_TEST_SESSION="+session_date.isoformat(),flush=True)
    print("NAVER_CLOSE_TEST_SCOPE=one_naver_GET_one_groq_POST_no_DB_no_UI",flush=True)
    news=fetch_naver()
    if news is None:return 2
    print("NAVER_CLOSE_TEST_FETCHED="+str(len(news)),flush=True)
    chosen=select(news,session_date)
    print("NAVER_CLOSE_TEST_SELECTED="+str(len(chosen)),flush=True)
    for i,row in enumerate(chosen):
        print("NAVER_CLOSE_TEST_SOURCE="+json.dumps({
            "id":i+1,"published_kst":row["published_kst"],
            "title":row["title"][:200],"description":row["description"][:260],
            "url":row["url"][:380],
        },ensure_ascii=False),flush=True)
    if len(chosen)<2:
        print("NAVER_CLOSE_TEST_ERROR=insufficient_matching_session_news_AI_not_called",flush=True)
        return 3
    return 0 if generate(chosen) else 4

if __name__=="__main__":
    sys.exit(main())
