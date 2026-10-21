"""Read-only Alpaca news article count for NVDA, SPCX and AAPL (last 24 h).
Temporary test; no database, service, application or credential writes."""
import datetime as dt
import json
import os
import urllib.request
import urllib.parse
import urllib.error

NOW=dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
START=NOW-dt.timedelta(hours=24)
def fmt(d): return d.isoformat().replace("+00:00","Z")
print("NEWS_COUNT_WINDOW_START_UTC="+fmt(START),flush=True)
print("NEWS_COUNT_WINDOW_END_UTC="+fmt(NOW),flush=True)
key=os.getenv("APCA_API_KEY_ID","").strip()
secret=os.getenv("APCA_API_SECRET_KEY","").strip()
if not key or not secret:
    print("NEWS_COUNT_ERROR=alpaca_credentials_not_available_in_readonly_job",flush=True)
else:
    for sym in ("NVDA","SPCX","AAPL"):
        ids=set()
        count=0
        pages=0
        token=None
        error=None
        while pages<20:
            qs={"symbols":sym,"start":fmt(START),"end":fmt(NOW),"sort":"asc","limit":50,"include_content":"false"}
            if token:qs["page_token"]=token
            req=urllib.request.Request("https://data.alpaca.markets/v1beta1/news?"+urllib.parse.urlencode(qs),headers={"APCA-API-KEY-ID":key,"APCA-API-SECRET-KEY":secret,"Accept":"application/json"},method="GET")
            try:
                with urllib.request.urlopen(req,timeout=15) as res:
                    data=json.load(res)
            except urllib.error.HTTPError as ex:
                error="http_"+str(ex.code)
                break
            except (urllib.error.URLError,TimeoutError,ValueError,OSError) as ex:
                error="request_or_json_"+type(ex).__name__
                break
            arr=data.get("news")
            if not isinstance(arr,list):
                error="invalid_news_response"
                break
            pages+=1
            for a in arr:
                if isinstance(a,dict):
                    identity=str(a.get("id") or a.get("url") or "")
                    if identity:
                        ids.add(identity)
                    else:
                        count+=1
            token=data.get("next_page_token")
            if not token:break
        total=len(ids)+count
        print("NEWS_24H_RESULT="+json.dumps({"symbol":sym,"count":total,"pages":pages,"complete":error is None and not token,"error":error},sort_keys=True),flush=True)
print("NEWS_24H_READONLY_COMPLETE",flush=True)
