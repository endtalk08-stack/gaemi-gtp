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
