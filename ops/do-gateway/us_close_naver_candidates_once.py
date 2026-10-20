"""One-time read-only Naver USA close-news candidate finder: three GETs max.
Bounded to 2026-10-20 05:00-14:00 KST, US session 2026-10-19.
No AI, news worker, database, render or saved state changes.
"""
import datetime as dt
from email.utils import parsedate_to_datetime
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

KST=ZoneInfo("Asia/Seoul")
QUERIES=["뉴욕증시 혼조 마감","뉴욕증시 반도체 반등 마감","나스닥 다우 19일 마감"]
START=dt.datetime(2026,10,20,5,0,tzinfo=KST)
END=dt.datetime(2026,10,20,15,0,tzinfo=KST)
NEWS=re.compile(r"뉴욕증시|미국\s*증시|미\s*증시|나스닥|S&P\s*500|다우존스|월가|美증시|美\s*증시",re.I)
MARKET=re.compile(r"마감|혼조|반등|상승|하락|급등|급락|종가|뉴욕증시",re.I)
KOREA=re.compile(r"코스피|코스닥|삼성전자|국장|코스피200|한국\s*증시|서울\s*증시|국내\s*증시",re.I)
def clean(v):return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]*>","",str(v or "")))).strip()
def main():
    id=os.getenv("NAVER_CLIENT_ID","").strip()
    key=os.getenv("NAVER_CLIENT_SECRET","").strip()
    if not id or not key:
        print("CANDIDATES_ERROR=naver_keys_missing");return 2
    print("CANDIDATES_SCOPE=3_queries_20261020_0500_to_1500_KST_no_AI",flush=True)
    seen=set();out=[]
    for q in QUERIES:
        url="https://naverapihub.apigw.ntruss.com/search/v1/news?"+urllib.parse.urlencode(
            {"query":q,"display":100,"start":1,"sort":"date","format":"json"})
        req=urllib.request.Request(url,headers={"X-NCP-APIGW-API-KEY-ID":id,
            "X-NCP-APIGW-API-KEY":key,"User-Agent":"gaemi-usclose-candidate-probe/1.0"})
        try:
            with urllib.request.urlopen(req,timeout=10) as resp:
                obj=json.loads(resp.read(500000))
            rows=obj.get("items") or []
            print("CANDIDATES_QUERY="+json.dumps({"q":q,"count":len(rows)},ensure_ascii=False),flush=True)
        except urllib.error.HTTPError as exc:
            print("CANDIDATES_QUERY_ERROR="+str(exc.code),flush=True);continue
        except Exception as exc:
            print("CANDIDATES_QUERY_ERROR="+type(exc).__name__,flush=True);continue
        for x in rows:
            try: pub=parsedate_to_datetime(str(x.get("pubDate") or "")).astimezone(KST)
            except Exception:continue
            if not START<=pub<END:continue
            title=clean(x.get("title"))
            desc=clean(x.get("description"))
            link=str(x.get("originallink") or x.get("link") or "").strip()
            if not NEWS.search(title) or not MARKET.search(title) or KOREA.search(title):continue
            if not link.startswith(("https://","http://")) or link in seen:continue
            seen.add(link)
            out.append({"published":pub.isoformat(timespec="minutes"),"title":title[:180],
                        "description":desc[:220],"url":link[:480],"query":q})
    out.sort(key=lambda x:x["published"])
    print("CANDIDATES_FOUND="+str(len(out)),flush=True)
    for x in out[:25]:
        print("CANDIDATES_ITEM="+json.dumps(x,ensure_ascii=False),flush=True)
    print("CANDIDATES_COMPLETE",flush=True)
    return 0
if __name__=="__main__":sys.exit(main())
