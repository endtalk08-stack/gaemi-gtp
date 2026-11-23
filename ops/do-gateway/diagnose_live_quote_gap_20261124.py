#!/usr/bin/env python3
"""Read-only. Verify actual quote endpoints and recent feed errors, not just /health."""
import datetime, json, urllib.request, urllib.error, subprocess, collections
from zoneinfo import ZoneInfo
print("CHECK_UTC", datetime.datetime.now(datetime.timezone.utc).isoformat(), flush=True)
print("CHECK_ET", datetime.datetime.now(ZoneInfo("America/New_York")).isoformat(), flush=True)
for unit in ("gaemigtp-kiwoom-us-top20-api.service", "gaemigtp-kiwoom-us-top20-https.service"):
    r=subprocess.run(["systemctl","show",unit,"-p","ActiveState","-p","MainPID","-p","SubState"],
                     capture_output=True,text=True,timeout=6)
    print("UNIT",unit,r.stdout.strip().replace(chr(10),";"),flush=True)
paths=("/health","/market/trading-value?market=us",
       "/market/us-etf-quotes","/market/us-industry-etf-quotes",
       "/market/us-industries?view=heatmap&include_stocks=1")
for origin in ("http://127.0.0.1:8765","https://quotes.gaemigtp.com"):
    for path in paths:
        if origin.startswith("https") and path.endswith("include_stocks=1"):
            continue
        try:
            req=urllib.request.Request(origin+path,headers={"User-Agent":"gaemigtp-readonly-restore-check/1.0"})
            with urllib.request.urlopen(req,timeout=23) as response:
                code=response.status
                data=json.load(response)
            items=data.get("items",[]) if isinstance(data,dict) else []
            etfs=data.get("etf_quotes",[]) if isinstance(data,dict) else []
            counts=collections.Counter()
            for q in items:
                if not isinstance(q,dict):continue
                counts["item_total"]+=1
                if isinstance(q.get("price"),(int,float)):counts["item_price"]+=1
                if isinstance(q.get("change_pct"),(int,float)):counts["item_change"]+=1
                if q.get("stale") is True:counts["item_stale"]+=1
                if isinstance(q.get("stocks"),list):
                    counts["stock_total"]+=len(q["stocks"])
                    counts["stock_rate"]+=sum(isinstance(s,dict) and isinstance(s.get("change_pct"),(int,float)) for s in q["stocks"])
            for q in etfs:
                if isinstance(q,dict):
                    counts["sector_etf_total"]+=1
                    if isinstance(q.get("change_pct"),(int,float)):counts["sector_etf_rates"]+=1
            print("API",origin,path,"status",code,"ok",data.get("ok"),"counts",json.dumps(dict(counts),sort_keys=True),flush=True)
        except Exception as e:
            print("API_ERROR",origin,path,type(e).__name__,str(e)[:120],flush=True)
for unit in ("gaemigtp-kiwoom-us-top20-api.service","gaemigtp-kiwoom-us-top20-https.service"):
    proc=subprocess.run(["journalctl","-u",unit,"--since","12 minutes ago","-n","85","--no-pager","-o","cat"],
                        capture_output=True,text=True,timeout=10)
    lines=[line for line in proc.stdout.splitlines() if any(x in line.upper() for x in
        ("KIWOOM_","TRACEBACK","ERROR","EXCEPTION","FAILED","CONNECTED","REGISTERED"))]
    print("RECENT_LOG_MARKERS",unit,len(lines),flush=True)
    for line in lines[-22:]:
        # Keep only system/event names, no API payload or credentials
        label=line.strip()
        if "KIWOOM_" in label:
            label=label[label.index("KIWOOM_"):][:110]
        elif "Traceback" in label:
            label="Traceback"
        elif "Error" in label or "ERROR" in label:
            label="Error in service log"
        else:
            continue
        print("RECENT_MARKER",label,flush=True)
print("LIVE_DIAGNOSTIC_DONE",flush=True)
