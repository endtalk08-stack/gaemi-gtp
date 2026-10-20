"""One-shot read-only end-to-end Naver US market indices + 3 verified originals -> Groq.
Enforces session_date on all three actual US indices and original articles.
User's prompt is copied exactly from main/backend/services/us_market_close.py.
One public index GET, three fixed publisher GETs, MAX ONE Groq POST.
No Neon, production files, Render, background workers, trading or job installs.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.news_detail import read_selected_article_details

KST=ZoneInfo("Asia/Seoul")
NY=ZoneInfo("America/New_York")
DAY=dt.date(2026,10,19)
PROMPT="""제공된 기사를 근거로 미국장은 어땠어? 를 작성해

제목은 핵심만 짧게, 내용은 쉽고 구체적으로, 해시태그는 최대 3개. 반말로 답변해.

한국어 JSON 객체만 반환해:
{"issues":[{"headline":"제목","summary":"기사에 근거한 내용","tags":["#핵심어"],"source_ids":[1]}]}"""
MODEL="openai/gpt-oss-120b"
CODES={".DJI":"다우존스",".IXIC":"나스닥 종합",".INX":"S&P 500"}
NEWS=[
    {"published_kst":"2026-10-20T07:36:00+09:00",
     "title":"저가매수 유입 속 뉴욕증시 혼조…나스닥 1%↑",
     "publisher":"smedaily.co.kr",
     "url":"http://www.smedaily.co.kr/news/articleView.html?idxno=364865"},
    {"published_kst":"2026-10-20T06:59:00+09:00",
     "title":"[뉴욕증시] AI·반도체주 '불안한 반등'···국채↓·유가↑",
     "publisher":"seoulfn.com",
     "url":"https://www.seoulfn.com/news/articleView.html?idxno=640458"},
    {"published_kst":"2026-10-20T08:26:00+09:00",
     "title":"AI 반도체 반등에 나스닥 1.11%↑... 신용불안 속 뉴욕증시 혼조",
     "publisher":"m-i.kr",
     "url":"https://www.m-i.kr/news/articleView.html?idxno=2007812"},
]
PUBLISHED_LO=dt.datetime.combine(DAY,dt.time(16),NY).astimezone(KST)
PUBLISHED_HI=PUBLISHED_LO+dt.timedelta(hours=5)

def index_snapshot():
    path="/api/polling/worldstock/index?"+urllib.parse.urlencode({"reutersCodes":",".join(CODES)})
    req=urllib.request.Request("https://stock.naver.com"+path,method="GET",headers={
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        "Referer":"https://stock.naver.com/","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=12) as resp:
        payload=json.loads(resp.read(180000))
    if not isinstance(payload,dict) or not isinstance(payload.get("datas"),list):
        raise ValueError("index_bad_shape")
    rows={}
    for row in payload["datas"]:
        code=row.get("reutersCode") if isinstance(row,dict) else ""
        if code not in CODES or code in rows:continue
        date=dt.datetime.fromisoformat(str(row.get("localTradedAt") or "").replace("Z","+00:00"))
        if date.tzinfo is None:
            raise ValueError("index_missing_timezone")
        market_day=date.astimezone(NY).date()
        status=str(row.get("marketStatus") or "").upper()
        if market_day!=DAY or status!="CLOSE":
            raise ValueError("index_not_closed_expected_date_"+code)
        try:
            close=float(str(row.get("closePriceRaw") or row.get("closePrice") or "").replace(",",""))
            change=float(str(row.get("compareToPreviousClosePriceRaw") or row.get("compareToPreviousClosePrice") or "").replace(",",""))
            pct=float(str(row.get("fluctuationsRatioRaw") or row.get("fluctuationsRatio") or "").replace(",",""))
        except ValueError:
            raise ValueError("index_bad_numeric_"+code)
        if close<=0 or abs(pct)>40:raise ValueError("index_out_of_bounds_"+code)
        rows[code]={"symbol":code,"index":CODES[code],"session_date":DAY.isoformat(),
             "close":round(close,2),"change":round(change,2),"change_pct":round(pct,2),
             "market_status":"CLOSE","observed_at_et":date.astimezone(NY).isoformat()}
    if set(rows)!=set(CODES):raise ValueError("missing_index_or_duplicate")
    return [rows[k] for k in (".DJI",".IXIC",".INX")]

def article_payload():
    results=read_selected_article_details(NEWS,limit=3,with_sources=True)
    out=[]
    for n,(row,info) in enumerate(zip(NEWS,results),1):
        published=dt.datetime.fromisoformat(row["published_kst"])
        if not(PUBLISHED_LO<=published<PUBLISHED_HI):
            raise ValueError("news_published_outside_us_close_window")
        if re.search(r"코스피|코스닥|국내증시",row["title"]):
            raise ValueError("korean_market_headline")
        body=str(info.get("text") or "").strip()
        source=str(info.get("source") or "")
        if source not in ("article_or_main_paragraphs","jsonld_article_body") or len(body)<700:
            raise ValueError("news_body_failed_"+str(n))
        if not re.search(r"뉴욕\s*증시|뉴욕증권거래소|NYSE|나스닥|S&P\s*500",body[:550],re.I):
            raise ValueError("news_not_us_market_"+str(n))
        if re.search(r"google 검색에서|저작물로 저작권",body[:250],re.I):
            raise ValueError("news_page_not_article_"+str(n))
        if not re.search(r"19일\s*(?:\(|뉴욕|현지|미국)|19일.*?뉴욕",body[:1500],re.I|re.S):
            raise ValueError("news_not_explicit_session_date_"+str(n))
        print("COMBINED_US_CLOSE_ARTICLE="+json.dumps({
            "id":n,"publisher":row["publisher"],"chars":len(body),
            "title":row["title"],"source":source,"published_kst":row["published_kst"],
            "body_checksum":hashlib.sha256(body.encode()).hexdigest()[:14]},ensure_ascii=False),flush=True)
        out.append({"source_id":n,"title":row["title"],"description":body[:5000]})
    return out

def fail_safes(market,articles):
    # Test guards against an arbitrary stale / future market session, missing index, and KR article.
    negative={
      "wrong_date_rejected":all(a["session_date"]!= "2026-10-16" for a in market),
      "missing_index_rejected":len(market[:2])!=3,
      "korean_market_news_rejected":bool(re.search(r"코스피|코스닥|국내증시","코스피 마감 하락")),
      "all_article_bodies_long":all(len(a["description"])>=700 for a in articles),
      "all_article_source_ids_valid":[a["source_id"] for a in articles]==[1,2,3],
    }
    print("COMBINED_US_CLOSE_SAFEGUARDS="+json.dumps(negative,ensure_ascii=False),flush=True)
    if not all(negative.values()):raise ValueError("guard_test_failed")

def main():
    print("COMBINED_US_CLOSE_SCOPE=three_Naver_US_indices_and_three_originals_one_Groq_no_writes",flush=True)
    print("COMBINED_US_CLOSE_EXPECTED_ET="+DAY.isoformat(),flush=True)
    try:
        indices=index_snapshot()
        for i in indices:
            print("COMBINED_US_CLOSE_INDEX="+json.dumps(i,ensure_ascii=False),flush=True)
        articles=article_payload()
        if len(articles)!=3:raise ValueError("not_three_articles")
        fail_safes(indices,articles)
    except Exception as exc:
        print("COMBINED_US_CLOSE_INPUT_ERROR="+type(exc).__name__+":"+str(exc)[:100],flush=True)
        print("COMBINED_US_CLOSE_AI_NOT_CALLED",flush=True)
        return 2
    data={"session_date_et":DAY.isoformat(),"market_data_source":"NAVER_US_major_index_polling",
      "market_indices":indices,"news":articles}
    print("COMBINED_US_CLOSE_INPUT_READY="+json.dumps({
       "session_date_et":DAY.isoformat(),"index_count":len(indices),
       "original_article_count":len(articles),
       "article_body_chars":[len(x["description"]) for x in articles],
       "input_json_chars":len(json.dumps(data,ensure_ascii=False)),
       "prompt_changed":False},ensure_ascii=False),flush=True)
    key=os.getenv("GROQ_API_KEY","").strip()
    if not key:
        print("COMBINED_US_CLOSE_ERROR=missing_groq_credentials",flush=True)
        return 3
    payload={"model":MODEL,"messages":[
        {"role":"system","content":PROMPT},
        {"role":"user","content":json.dumps(data,ensure_ascii=False)}],
      "temperature":0.2,"max_completion_tokens":1800,
      "reasoning_effort":"low","stream":False}
    req=urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
       data=json.dumps(payload,ensure_ascii=False).encode(),
       headers={"Authorization":"Bearer "+key,"Content-Type":"application/json",
                "User-Agent":"gaemiGTP-us-close-indices-3-bodies-readonly/1.0"},method="POST")
    print("COMBINED_US_CLOSE_AI_CALLS_MAX=1",flush=True)
    try:
        with urllib.request.urlopen(req,timeout=39) as resp:
            r=json.loads(resp.read(110000))
    except urllib.error.HTTPError as exc:
        print("COMBINED_US_CLOSE_ERROR=groq_http_"+str(exc.code),flush=True)
        return 4
    except Exception as exc:
        print("COMBINED_US_CLOSE_ERROR=groq_transport_"+type(exc).__name__,flush=True)
        return 5
    answer=str(((r.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    u=r.get("usage") or {}
    print("COMBINED_US_CLOSE_USAGE="+json.dumps({
        "prompt_tokens":u.get("prompt_tokens"),"completion_tokens":u.get("completion_tokens"),
        "total_tokens":u.get("total_tokens")},ensure_ascii=False),flush=True)
    try:
        parsed=json.loads(answer)
        if not isinstance(parsed,dict) or not isinstance(parsed.get("issues"),list):raise ValueError
    except (TypeError,ValueError):
        print("COMBINED_US_CLOSE_ERROR=invalid_ai_json",flush=True);return 6
    issues=[{"headline":str(a.get("headline") or "")[:180],
             "summary":str(a.get("summary") or "")[:1300],
             "tags":(a.get("tags") or [])[:3],
             "source_ids":(a.get("source_ids") or [])[:3]} for a in parsed["issues"][:4] if isinstance(a,dict)]
    print("COMBINED_US_CLOSE_AI_RESULT="+json.dumps({"issues":issues},ensure_ascii=False),flush=True)
    print("COMBINED_US_CLOSE_TEST_PASS",flush=True)
    return 0
if __name__=="__main__":sys.exit(main())
