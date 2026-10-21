"""One-shot read-only NAVER initial-50 receipt count for US missing-news stocks.
No Neon writes, AI calls, article contents, or service changes.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.analysis.news.catalog import STOCK_UNIVERSE, canonical_us_news_name

BASE = "https://naverapihub.apigw.ntruss.com/search/v1/news"
TARGETS = (
    ("AMD", "AMD"),
    ("SMCI", "슈퍼 마이크로 컴퓨터"),
    ("CRCL", "써클 인터넷 그룹"),
    ("SMR", "뉴스케일 파워"),
    ("TSM", "TSMC ADR"),
    ("PLTR", "팔란티어 테크놀로지스"),
)
def parsed_time(item):
    stamp = item.get("pubDate")
    try:
        dt = parsedate_to_datetime(str(stamp or ""))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except (ValueError, TypeError, IndexError, OverflowError):
        return None

def main():
    key = os.getenv("NAVER_CLIENT_ID", "").strip()
    secret = os.getenv("NAVER_CLIENT_SECRET", "").strip()
    print("NAVER_INITIAL50_DIAGNOSTIC_BEGIN", flush=True)
    print("NAVER_CREDENTIALS_CONFIGURED=" + ("YES" if key and secret else "NO"), flush=True)
    if not key or not secret:
        print("NAVER_INITIAL50_DIAGNOSTIC_STOP=no_credentials", flush=True)
        return
    now = datetime.now(timezone.utc)
    cutoff = now-timedelta(hours=24)
    print("CHECK_UTC=" + now.isoformat(), flush=True)
    headers = {"X-NCP-APIGW-API-KEY-ID":key, "X-NCP-APIGW-API-KEY":secret,
               "User-Agent":"gaemiGTP/1.0"}
    for symbol,display in TARGETS:
        canonical = canonical_us_news_name(display)
        aliases = STOCK_UNIVERSE.get("미국",{}).get(canonical) or []
        queries = list(dict.fromkeys([canonical]+aliases))
        all_rows=[]
        responses=0
        failed=0
        for query in queries:
            params = urllib.parse.urlencode({"query":query,"display":50,"start":1,"sort":"date","format":"json"})
            request=urllib.request.Request(BASE+"?"+params,headers=headers)
            try:
                with urllib.request.urlopen(request,timeout=4) as response:
                    body=json.loads(response.read().decode("utf-8"))
                rows=body.get("items",[]) if isinstance(body,dict) else []
                if not isinstance(rows,list):
                    raise ValueError("items_not_list")
                total=body.get("total") if isinstance(body,dict) else None
                responses+=1
                all_rows.extend(row for row in rows if isinstance(row,dict))
                print("QUERY "+json.dumps({"stock":display,"ticker":symbol,"q":query,
                      "requested":50,"returned":len(rows),"provider_total":total},ensure_ascii=False),flush=True)
            except Exception as exc:
                failed+=1
                print("QUERY "+json.dumps({"stock":display,"ticker":symbol,"q":query,
                      "requested":50,"error_type":type(exc).__name__,
                      "http_status":getattr(exc,"code",None)},ensure_ascii=False),flush=True)
        unique={}
        for row in all_rows:
            link=str(row.get("originallink") or row.get("link") or "").strip()
            if link and link not in unique:
                unique[link]=row
        fresh24=sum(1 for row in unique.values()
                    if (dt:=parsed_time(row)) is not None and cutoff<=dt<=now)
        print("STOCK "+json.dumps({"stock":display,"ticker":symbol,"canonical":canonical,
               "queries":len(queries),"successful_queries":responses,"failed_queries":failed,
               "raw_returned_sum":len(all_rows),"unique_urls":len(unique),
               "unique_published_in_24h":fresh24},ensure_ascii=False),flush=True)
    print("NAVER_INITIAL50_DIAGNOSTIC_END",flush=True)
if __name__=="__main__":
    main()
