"""Isolated, read-only US-close automatic article-selection + ORIGINAL BODY quality audit.

Exactly three NAVER search GETs; read max 36 publisher links once each.
US session: 2026-10-19; publish window: 2026-10-20 05:00-10:00 KST.
Existing backend.services.news_detail reader; no AI calls / DB / writes / deployments.
Print bounded audit results, selected source IDs + what AI input WOULD contain.
Do not treat meta descriptions or irrelevant HTML as article bodies.
"""
import datetime as dt
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.services.news_detail import read_selected_article_details

KST=ZoneInfo("Asia/Seoul")
NY=ZoneInfo("America/New_York")
DAY=dt.date(2026,10,19)
CLOSE=dt.datetime.combine(DAY,dt.time(16),NY).astimezone(KST)
CUTOFF=CLOSE+dt.timedelta(hours=5)
# Queries intentionally describe the *completed US market session*, never KOSPI.
QUERIES=("뉴욕증시 혼조 마감","나스닥 다우 19일 마감","뉴욕증시 반도체 반등 마감")
USA_TITLE=re.compile(r"뉴욕\s*증시|미국\s*증시|미\s*증시|美\s*증시|나스닥|다우존스",re.I)
CLOSE_TITLE=re.compile(r"마감|혼조|반등|상승|하락",re.I)
DOMESTIC_TITLE=re.compile(r"코스피|코스닥|국장|한국\s*증시|국내\s*증시|삼성전자|SK하이닉스|코스피200",re.I)
BEFORE_CLOSE=re.compile(r"개장|장중|선물|프리마켓|장전|전망|예상|오늘의\s*증시\s*전략",re.I)
USA_BODY=re.compile(r"뉴욕\s*증시|미국\s*증시|뉴욕증권거래소|NYSE|나스닥|다우존스|S&P\s*500",re.I)
INDEX_MARKERS=[re.compile(r"나스닥",re.I),re.compile(r"다우(?:존스)?",re.I),re.compile(r"S&P\s*500|스탠더드앤드푸어스",re.I)]
TOPICS=["반도체","AI","인공지능","기술주","금리","국채","유가","원유","프랑스","중동","경기","매수","실적","수익성"]
BAN_BODY=re.compile(r"Google 검색에서|모든 콘텐츠는.{0,100}저작물|이용약관|개인정보처리방침",re.I)

def clean(v):
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>"," ",str(v or "")))).strip()

def host(url):
    return (urllib.parse.urlsplit(url).hostname or "").lower().removeprefix("www.")

def canonical(url):
    p=urllib.parse.urlsplit(url)
    # Trim navigation tracking parameters but retain actual article IDs.
    q=urllib.parse.parse_qsl(p.query,keep_blank_values=False)
    q=[(k,v) for k,v in q if k.lower() in ("idxno","newsid","articleid","ud","no","id","news_id","newsid","mediacodeno")]
    return (p.hostname or "").lower()+p.path.rstrip("/")+"?"+urllib.parse.urlencode(sorted(q))

def fetch_candidates():
    key=os.getenv("NAVER_CLIENT_ID","").strip()
    secret=os.getenv("NAVER_CLIENT_SECRET","").strip()
    if not key or not secret:raise RuntimeError("naver_keys_missing")
    found={}
    stats={"raw_rows":0,"window":0,"headline_us":0,"headline_rejected":0}
    for q in QUERIES:
        url="https://naverapihub.apigw.ntruss.com/search/v1/news?"+urllib.parse.urlencode({
            "query":q,"display":100,"start":1,"sort":"date","format":"json"})
        req=urllib.request.Request(url,method="GET",headers={
            "X-NCP-APIGW-API-KEY-ID":key,"X-NCP-APIGW-API-KEY":secret,
            "User-Agent":"gaemi-usclose-originals-selection-audit/1.0",
        })
        try:
            with urllib.request.urlopen(req,timeout=10) as resp:
                payload=json.loads(resp.read(650000))
        except urllib.error.HTTPError as exc:
            print("US_SELECTOR_NEWS_QUERY_HTTP="+str(int(exc.code)),flush=True)
            continue
        except Exception as exc:
            print("US_SELECTOR_NEWS_QUERY_ERROR="+type(exc).__name__,flush=True)
            continue
        items=payload.get("items") if isinstance(payload,dict) else None
        if not isinstance(items,list):
            print("US_SELECTOR_NEWS_BAD_JSON_ARRAY",flush=True)
            continue
        print("US_SELECTOR_QUERY="+json.dumps({"query":q,"count":len(items)},ensure_ascii=False),flush=True)
        stats["raw_rows"]+=len(items)
        for a in items:
            if not isinstance(a,dict):continue
            try:published=parsedate_to_datetime(str(a.get("pubDate") or "")).astimezone(KST)
            except Exception:continue
            if not CLOSE<=published<CUTOFF:continue
            stats["window"]+=1
            title=clean(a.get("title"))
            desc=clean(a.get("description"))
            url=str(a.get("originallink") or a.get("link") or "").strip()
            if not USA_TITLE.search(title) or not CLOSE_TITLE.search(title):continue
            stats["headline_us"]+=1
            if DOMESTIC_TITLE.search(title) or BEFORE_CLOSE.search(title):
                stats["headline_rejected"]+=1
                continue
            if not url.startswith(("https://","http://")):continue
            if host(url) in ("naver.com","news.naver.com") or not host(url):continue
            can=canonical(url)
            score=0
            for pat,n in ((r"뉴욕\s*증시",4),(r"마감",3),(r"혼조",2),(r"다우",1),
                         (r"나스닥",1),(r"S&P",1),(r"반도체",2),(r"AI|금리|유가",1)):
                score+=int(bool(re.search(pat,title,re.I)))*n
            # Headlines explicitly containing closing index facts get some priority.
            if "속보" in title:score-=3
            entry={"title":title,"snippet":desc,"url":url,"publisher":host(url),
                   "published_kst":published.isoformat(timespec="minutes"),"headline_score":score}
            found.setdefault(can,entry)
    print("US_SELECTOR_SCAN="+json.dumps({**stats,"unique_us_headlines":len(found),
        "window_start_kst":CLOSE.isoformat(timespec="minutes"),
        "window_end_kst":CUTOFF.isoformat(timespec="minutes")},ensure_ascii=False),flush=True)
    return sorted(found.values(),key=lambda x:(-x["headline_score"],x["published_kst"]))[:36]

def classify(a, body, source):
    if source not in ("jsonld_article_body","article_or_main_paragraphs"):
        return "unverified_extraction"
    if len(body)<700:return "short_body_or_fallback"
    if BAN_BODY.search(body[:400]):return "page_chrome"
    start=body[:500]
    if not USA_BODY.search(start):
        return "unrelated_body_start"
    if len(USA_BODY.findall(body[:1800]))<2:
        return "weak_us_market_evidence"
    title=a["title"]
    matched=sum(1 for t in TOPICS if re.search(re.escape(t),title,re.I) and re.search(re.escape(t),body,re.I))
    indexes=sum(bool(p.search(body)) for p in INDEX_MARKERS)
    if indexes<2:return "insufficient_index_evidence"
    if matched<1:return "title_body_mismatch"
    if not re.search(r"마감|거래를\s*마쳤|장을\s*마쳤|종가|하락|상승|혼조",body[:1500]):
        return "not_closing_article"
    return "accepted"

def category(a,body):
    text=a["title"]+" "+body[:500]
    if re.search(r"금리|국채|유가|중동|프랑스",a["title"]):return "rates_oil"
    if re.search(r"반도체|AI|인공지능|기술주",a["title"],re.I):return "technology"
    return "market"

def main():
    print("US_SELECTOR_SCOPE=3_NAVER_GET_36_publisher_GET_max_no_AI_no_db_no_ui",flush=True)
    candidate=fetch_candidates()
    print("US_SELECTOR_TOP_TO_READ="+str(len(candidate)),flush=True)
    if not candidate:
        print("US_SELECTOR_ERROR=no_candidates",flush=True)
        return 2
    # Bound by reader's existing max three concurrent operations; URL fetches 15 max.
    reads=read_selected_article_details(
        [{"url":a["url"]} for a in candidate],limit=len(candidate),with_sources=True)
    accepted=[]
    reasons={}
    for a,r in zip(candidate,reads):
        source=str(r.get("source") or "fetch_failed")
        body=str(r.get("text") or "").strip()
        reason=classify(a,body,source)
        reasons[reason]=reasons.get(reason,0)+1
        summary={"title":a["title"][:120],"publisher":a["publisher"],
                 "source":source,"body_chars":len(body),
                 "decision":reason}
        print("US_SELECTOR_AUDIT="+json.dumps(summary,ensure_ascii=False),flush=True)
        if reason=="accepted":
            entry=dict(a,body=body,source=source,category=category(a,body))
            accepted.append(entry)
    # Reject duplicate page bodies; require different publishers and subject variety.
    by_subject={"market":[],"technology":[],"rates_oil":[]}
    dedup=[]
    for a in sorted(accepted,key=lambda x:(len(x["body"]),x["headline_score"]),reverse=True):
        if any(a["publisher"]==p["publisher"] or
               SequenceMatcher(None,a["body"][:1200],p["body"][:1200]).ratio()>=0.78 or
               SequenceMatcher(None,a["title"],p["title"]).ratio()>=0.82
               for p in dedup):
            continue
        dedup.append(a)
        by_subject[a["category"]].append(a)
    final=[]
    # Diversify: market, rates/oil, semis, while retaining source credibility/quality.
    for topic in ("market","rates_oil","technology"):
        options=[a for a in by_subject[topic] if a not in final]
        if options:
            final.append(max(options,key=lambda a:(len(a["body"]),a["headline_score"])))
    for a in dedup:
        if len(final)>=3:break
        if a not in final:final.append(a)
    final=final[:3]
    print("US_SELECTOR_AUDIT_COUNTS="+json.dumps({
        "attempted_originals":len(candidate),"raw_body_quality_accepted":len(accepted),
        "unique_body_accepted":len(dedup),"selected":len(final),
        "rejected_by_reason":{k:v for k,v in reasons.items() if k!="accepted"},
        "topics":[a["category"] for a in final],
    },ensure_ascii=False),flush=True)
    payload=[]
    for i,a in enumerate(final,1):
        # Keep exact existing _prompt() field shape, replacing description with full verified original.
        payload.append({"source_id":i,"title":a["title"],"description":a["body"][:5000]})
        print("US_SELECTOR_SELECTED="+json.dumps({
            "source_id":i,"title":a["title"],"url":a["url"],
            "publisher":a["publisher"],"published_kst":a["published_kst"],
            "category":a["category"],"extraction":a["source"],
            "body_chars":len(a["body"]),"body_sha256":hashlib.sha256(a["body"].encode("utf-8")).hexdigest()[:16],
            "body_preview":a["body"][:160],
        },ensure_ascii=False),flush=True)
    # Input contract verification: model receives complete article text rather than snippets.
    assert len(payload)<=3
    for p in payload:
        assert len(p["description"])>=700 and "source_id" in p
        assert not any(p["description"]==a["snippet"] for a in candidate)
        assert USA_BODY.search(p["description"][:500])
    size=len(json.dumps(payload,ensure_ascii=False))
    print("US_SELECTOR_AI_INPUT_READY="+json.dumps({
        "source_count":len(payload),"json_chars":size,
        "description_chars":[len(a["description"]) for a in payload],
        "source_ids":[a["source_id"] for a in payload],
        "description_is_verified_article_body":True,
        "groq_calls":0,
    },ensure_ascii=False),flush=True)
    if len(payload)<3:
        print("US_SELECTOR_ERROR=not_three_independently_verified_full_articles",flush=True)
        return 3
    print("US_SELECTOR_TEST_PASS",flush=True)
    return 0

if __name__=="__main__":sys.exit(main())
