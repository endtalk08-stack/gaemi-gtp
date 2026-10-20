"""One-off Naver US extended-hours data probe, read-only, no production changes.

Bounded to exactly 4 public GETs targeting NVDA.O and existing US listing.
No access to credentials/DB. No HTML body dumps; only compact JSON field audit.
"""
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://stock.naver.com"
PATHS = [
    ("NVDA_POLL", "/api/polling/worldstock/stock?reutersCodes=NVDA.O"),
    ("NVDA_BASIC", "/api/securityService/stock/NVDA.O/basic"),
    ("NVDA_ITEM_PRICE", "/api/stockSecurity/items/v1/foreign/prices?itemCodes=NVDA.O"),
    ("US_RANKING", "/api/stockSecurity/aggregate/foreignStock?type=listing&nationType=USA&size=2&index=0&sortType=tradingValue&sortDirection=desc&includeOverMarket=true"),
]
PRICING = re.compile(r"price|change|fluct|market|session|trade|time|timestamp|update|over|pre|post|after|close|date|status|delay|exchan|volume", re.I)
SENSITIVE = re.compile(r"cookie|password|token|secret|authorization|userid|account", re.I)

def audit(name, obj, max_values=80):
    print("NAVER_PROBE_TOP_TYPE=" + name + ":" + type(obj).__name__, flush=True)
    if isinstance(obj, dict):
        print("NAVER_PROBE_TOP_KEYS=" + name + ":" + ",".join(list(obj)[:60]),flush=True)
    elif isinstance(obj,list):
        print("NAVER_PROBE_LIST_LEN=" + name + ":" + str(len(obj)), flush=True)
    fields=[]
    def walk(p, v, depth):
        if len(fields)>=max_values or depth>4: return
        if isinstance(v,dict):
            for k,val in list(v.items())[:70]:
                if SENSITIVE.search(str(k)): continue
                path=p+"."+str(k)
                if isinstance(val,(dict,list)):
                    walk(path,val,depth+1)
                elif PRICING.search(str(k)):
                    fields.append((path,str(val)[:95]))
        elif isinstance(v,list):
            for i, child in enumerate(v[:2]):
                walk(p+"["+str(i)+"]",child,depth+1)
    walk("root",obj,0)
    print("NAVER_PROBE_FIELDS="+json.dumps({"source":name,"matched":fields},ensure_ascii=False),flush=True)

def main():
    print("NAVER_PROBE_UTC="+dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),flush=True)
    print("NAVER_PROBE_SCOPE=one_NVDA_4_readonly_requests",flush=True)
    successes=0
    for name,path in PATHS:
        req=urllib.request.Request(BASE+path, method="GET",headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
            "Referer":"https://stock.naver.com/",
            "Accept":"application/json",
        })
        try:
            with urllib.request.urlopen(req,timeout=10) as resp:
                data=json.loads(resp.read(450000))
            successes+=1
            print("NAVER_PROBE_STATUS="+name+":200",flush=True)
            audit(name,data)
        except urllib.error.HTTPError as exc:
            print("NAVER_PROBE_STATUS="+name+":"+str(int(exc.code)),flush=True)
        except Exception as exc:
            print("NAVER_PROBE_STATUS="+name+":ERROR_"+type(exc).__name__,flush=True)
    print("NAVER_PROBE_SUCCESS_COUNT="+str(successes),flush=True)
    print("NAVER_PROBE_COMPLETED",flush=True)
    return 0

if __name__=="__main__":
    sys.exit(main())
