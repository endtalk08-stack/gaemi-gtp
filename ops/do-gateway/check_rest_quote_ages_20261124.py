#!/usr/bin/env python3
"""Read-only: verify whether REST fallback records can actually be rendered."""
import json, time, urllib.request, collections
base="https://quotes.gaemigtp.com"
for path in ("/market/trading-value?market=us","/market/us-industry-etf-quotes",
             "/market/us-etf-quotes","/market/us-industries?view=heatmap&include_stocks=1"):
    try:
        req=urllib.request.Request(base+path,headers={"User-Agent":"gaemigtp-readonly-diagnostic"})
        with urllib.request.urlopen(req,timeout=24) as r:data=json.load(r)
        items=data.get("items",[]) if isinstance(data,dict) else []
        age=[(time.time()*1000-q["received_at_ms"])/60000 for q in items
             if isinstance(q,dict) and isinstance(q.get("received_at_ms"),(int,float))]
        groups=collections.Counter(str(q.get("source")) for q in items if isinstance(q,dict))
        sessions=collections.Counter(str(q.get("reference_close_date")) for q in items if isinstance(q,dict))
        etfs=data.get("etf_quotes",[]) if isinstance(data,dict) else []
        print("REST_CHECK",path,"ok",data.get("ok"),"items",len(items),"etfs",len(etfs),
             "ages_min",round(min(age),1) if age else None,"ages_max",round(max(age),1) if age else None,
             "source",dict(groups),"reference_date",dict(sessions),flush=True)
        if "industries" in path:
            stocks=sum(len(q.get("stocks",[])) for q in items if isinstance(q,dict))
            with_pct=sum(1 for q in items for v in q.get("stocks",[]) if isinstance(v.get("change_pct"),(int,float)))
            print("REST_INDUSTRY_DETAIL",stocks,with_pct,"sector_rates",
                  sum(isinstance(v.get("change_pct"),(int,float)) for v in etfs),flush=True)
    except Exception as e:print("REST_CHECK_ERROR",path,type(e).__name__,str(e)[:90],flush=True)
print("READONLY_FALLBACK_AUDIT_DONE")
