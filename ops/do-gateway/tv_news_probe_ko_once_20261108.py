"""Exactly ONE TradingView news overall KO request, no writes or retries."""
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

def inactive(unit):
    p=subprocess.run(["systemctl","is-active",unit],text=True,capture_output=True,timeout=5)
    return p.stdout.strip()=="inactive"
for unit in ("gaemigtp-news.service","gaemigtp-tradingview-news.service"):
    if not inactive(unit):
        raise SystemExit("TV_STOP_WORKER_NOT_INACTIVE")
key=os.environ.get("TRADINGVIEW_API_KEY","").strip()
if not key:
    raise SystemExit("TV_STOP_AUTH_KEY_MISSING")
params={"lang":"ko","market_country":"US"}
url="https://api.tradingviewapi.com/api/news?"+urllib.parse.urlencode(params)
request=urllib.request.Request(url,method="GET",headers={
    "Authorization":"Bearer "+key,
    "Accept":"application/json",
    "User-Agent":"gaemiGTP-news-ko-probe/1.0",
})
print("TV_CALL_BUDGET=1 LANG=ko MARKET_COUNTRY=US FEED=overall",flush=True)
try:
    with urllib.request.urlopen(request,timeout=15) as response:
        status=response.status
        headers=response.headers
        raw=response.read(2500000)
except urllib.error.HTTPError as e:
    print("TV_REQUEST_STOP_HTTP_STATUS="+str(e.code)+" RETRY=0",flush=True)
    raise SystemExit(2)
except (urllib.error.URLError,TimeoutError,OSError) as e:
    print("TV_REQUEST_STOP_NETWORK_ERROR="+type(e).__name__+" RETRY=0",flush=True)
    raise SystemExit(2)
if status!=200:
    raise SystemExit("TV_REQUEST_STOP_UNEXPECTED_STATUS")
rate={k.lower():v for k,v in headers.items() if k.lower().startswith("x-ratelimit-") or k.lower()=="retry-after"}
payload=json.loads(raw.decode("utf-8"))
data=payload.get("data") if isinstance(payload,dict) else None
items=data.get("items") if isinstance(data,dict) else None
if not isinstance(payload,dict) or payload.get("success") is not True or not isinstance(items,list):
    raise SystemExit("TV_REQUEST_STOP_INVALID_SCHEMA")
titles=[str(x.get("title") or "").strip() for x in items if isinstance(x,dict)]
ko=sum(bool(re.search("[가-힣]",t)) for t in titles)
entries=[]
for x in items[:80]:
    if not isinstance(x,dict):
        continue
    title=str(x.get("title") or "")
    entries.append({
        "title":title[:220],
        "lang_has_ko":bool(re.search("[가-힣]",title)),
        "has_id":bool(x.get("id") or x.get("newsId")),
        "permission":str(x.get("permission") or "unset")[:32],
    })
# Run existing page classification on EVERY returned item; no writes.
import sys
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.services.tradingview_news_page import normalize_article, build_snapshot
from backend.providers.tradingview_news_detail import _get_detail, _extract_detail
from collections import Counter
classified=[]
for index,article in enumerate(items):
    if not isinstance(article,dict):
        continue
    row=dict(article)
    row["news_categories"]=["overall"]
    result=normalize_article(row)
    classified.append({"index":index+1,"title":str(result.get("title") or "")[:180],
      "section":result.get("news_section"),
      "category":(result.get("event_category") or {}).get("label"),
      "market_category":(result.get("market_event_category") or {}).get("label"),
      "stock_tags":[x.get("label") for x in result.get("stock_event_matches") or []],
      "market_tags":[x.get("label") for x in result.get("market_event_matches") or []],
      "symbols":(result.get("symbols") or [])[:8]})
counts=Counter((row["section"],row["category"]) for row in classified)
snapshot=build_snapshot([dict(x,news_categories=["overall"]) for x in items if isinstance(x,dict)])
print("TV_CLASSIFICATION_TOTAL="+str(len(classified))+" SNAPSHOT_ITEMS="+str(snapshot["count"]),flush=True)
print("TV_CLASSIFICATION_COUNTS="+json.dumps(
  [{"section":a,"category":b,"count":v} for (a,b),v in sorted(counts.items())],
  ensure_ascii=False,separators=(",",":")),flush=True)
for row in classified:
    print("TV_CLASSIFICATION_ITEM="+json.dumps(row,ensure_ascii=False,separators=(",",":")),flush=True)
# Only after classification has finished: exactly ONE detail call for the FIRST list item.
first=items[0] if items and isinstance(items[0],dict) else {}
first_id=str(first.get("id") or first.get("newsId") or "").strip()
if not first_id:
    print("TV_DETAIL_SKIPPED_FIRST_ARTICLE_MISSING_ID",flush=True)
else:
    print("TV_DETAIL_CALL_BUDGET=1 FIRST_ARTICLE_INDEX=1",flush=True)
    try:
        data_detail=_get_detail(first_id,key,urllib.request.urlopen)
        detail_values=_extract_detail(data_detail)
        body=str(detail_values.get("detail_body") or "")
        print("TV_FIRST_DETAIL_RESULT="+json.dumps({
          "title":str(first.get("title") or "")[:200],
          "id":first_id[:250],
          "body_chars":len(body),
          "body_korean_chars":len(re.findall("[가-힣]",body)),
          "summary_chars":len(str(detail_values.get("detail_summary") or "")),
          "permission":str(data_detail.get("permission") or first.get("permission") or ""),
          "data_keys":sorted(data_detail.keys())[:60],
          "detail_calls":1,"body_published":False
        },ensure_ascii=False,separators=(",",":")),flush=True)
    except urllib.error.HTTPError as e:
        print("TV_FIRST_DETAIL_HTTP_ERROR="+str(e.code)+" RETRY=0",flush=True)
    except (ValueError,TypeError,urllib.error.URLError,OSError) as e:
        print("TV_FIRST_DETAIL_ERROR="+type(e).__name__+" RETRY=0",flush=True)

report={
    "status":status,
    "query":params,
    "items":len(items),
    "ko_titles":ko,
    "ko_ratio":round(ko/max(len(titles),1),3),
    "title_samples":entries,
    "rate_headers":rate,
    "network_calls":1,
    "detail_calls":0,
    "cache_writes":0,
    "r2_writes":0,
}
print("TV_KO_NEWS_PROBE="+json.dumps(report,ensure_ascii=False,separators=(",",":")),flush=True)
for unit in ("gaemigtp-news.service","gaemigtp-tradingview-news.service"):
    if not inactive(unit):
        raise SystemExit("TV_STOP_WORKER_STATE_CHANGED")
print("TV_KO_NEWS_PROBE_DONE_ONE_CALL",flush=True)
