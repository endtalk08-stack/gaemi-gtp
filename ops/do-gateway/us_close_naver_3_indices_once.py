"""One-shot read-only audit of NAVER 3 actual US major market indices.
Exactly 4 public GETs: one index polling and three index daily history.
No credentials, DB, AI, worker changes, scheduling, or other tickers.
"""
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from zoneinfo import ZoneInfo

NY=ZoneInfo("America/New_York")
EXPECTED=dt.date(2026,10,19)
SYMBOLS={".DJI":"다우존스", ".IXIC":"나스닥 종합", ".INX":"S&P 500"}
KEY=re.compile(r"close|current|fluct|change|date|localTrade|time|status|delay|start|end|code|indexName|name|value|price|open|volume",re.I)

def request(path,label):
    url="https://stock.naver.com"+path
    req=urllib.request.Request(url,method="GET",headers={
        "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        "Referer":"https://stock.naver.com/","Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=12) as resp:
            payload=json.loads(resp.read(430000))
            print("INDEX3_HTTP="+label+":200",flush=True)
        return payload
    except urllib.error.HTTPError as exc:
        print("INDEX3_HTTP="+label+":"+str(int(exc.code)),flush=True)
    except (ValueError,urllib.error.URLError,TimeoutError,OSError) as exc:
        print("INDEX3_HTTP="+label+":error_"+type(exc).__name__,flush=True)
    return None

def date_of(v):
    if not v:return None
    try:
        value=dt.datetime.fromisoformat(str(v).replace("Z","+00:00"))
        if value.tzinfo: value=value.astimezone(NY)
        return value.date().isoformat()
    except (ValueError,TypeError):return None

def shallow(obj,n=45):
    if not isinstance(obj,dict):return {}
    return {str(k):v if isinstance(v,(str,int,float,bool,type(None))) else type(v).__name__
        for k,v in list(obj.items()) if KEY.search(str(k))} if obj else {}

def scan_rows(o):
    # Bounded generic audit; exact schema unknown before testing.
    if isinstance(o,list):return o[:2]
    if not isinstance(o,dict):return []
    for k in ("datas","prices","items","list","data","results","priceList","dailyPriceList"):
        v=o.get(k)
        if isinstance(v,list):return v[:2]
        if isinstance(v,dict):
            for sub in v.values():
                if isinstance(sub,list):return sub[:2]
    return []

def main():
    print("INDEX3_SCOPE=naver_dow_nasdaq_sp500_only_one_poll_three_history_no_writes",flush=True)
    print("INDEX3_EXPECTED_SESSION="+EXPECTED.isoformat(),flush=True)
    poll=request("/api/polling/worldstock/index?"+
      urllib.parse.urlencode({"reutersCodes":",".join(SYMBOLS)}),"poll")
    complete={}
    if isinstance(poll,dict):
        print("INDEX3_POLL_TOP_KEYS="+",".join(list(poll)[:25]),flush=True)
        for row in poll.get("datas",[])[:10]:
            if not isinstance(row,dict):continue
            code=str(row.get("reutersCode") or row.get("code") or "")
            if code not in SYMBOLS:
                print("INDEX3_POLL_UNKNOWN_CODE="+code[:40],flush=True)
                continue
            fields=shallow(row)
            recorded_date=date_of(row.get("localTradedAt"))
            status=str(row.get("marketStatus") or "")
            complete[code]=(recorded_date==EXPECTED.isoformat() and status.upper()=="CLOSE")
            print("INDEX3_POLL_ROW="+json.dumps({"symbol":code,"name":SYMBOLS[code],
               "values":fields,"session_date_et":recorded_date,
               "is_expected_closed_session":complete[code]},
              ensure_ascii=False,default=str),flush=True)
    else:
        print("INDEX3_POLL_INVALID",flush=True)
    for code,name in SYMBOLS.items():
        hist=request("/api/securityService/index/"+urllib.parse.quote(code,safe=".")+
          "/price?page=1&pageSize=3","history_"+code)
        if hist is None:continue
        print("INDEX3_HISTORY_TOP="+json.dumps({"symbol":code,"type":type(hist).__name__,
           "keys":list(hist)[:25] if isinstance(hist,dict) else [],"list_length":len(hist) if isinstance(hist,list) else None},ensure_ascii=False),flush=True)
        rows=scan_rows(hist)
        if not rows and isinstance(hist,dict):
            print("INDEX3_HISTORY_FIELDS="+json.dumps({"symbol":code,"values":shallow(hist)},ensure_ascii=False,default=str),flush=True)
        for i,r in enumerate(rows):
            if isinstance(r,dict):
                print("INDEX3_HISTORY_ROW="+json.dumps({"symbol":code,"row":i,"values":shallow(r),
                    "date_fields":{k:r.get(k) for k in r if "date" in k.lower() or "time" in k.lower()}},ensure_ascii=False,default=str),flush=True)
    print("INDEX3_EXPECTED_CLOSED_COUNT="+str(sum(complete.values())),flush=True)
    print("INDEX3_AUDIT_COMPLETE",flush=True)
    return 0

if __name__=="__main__":sys.exit(main())
