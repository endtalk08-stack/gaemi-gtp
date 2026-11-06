import os, json, urllib.request, urllib.parse
key=os.environ.get("TRADINGVIEW_API_KEY","").strip()
if not key: raise SystemExit("MISSING_KEY")
base="https://api.tradingviewapi.com/api/news/index"
for label,params in (("lang_ko",{"lang":"ko"}),("no_params",{})):
    url=base + (("?" + urllib.parse.urlencode(params)) if params else "")
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+key,"Accept":"application/json","User-Agent":"gaemiGTP-index-check/1.0"})
    with urllib.request.urlopen(req,timeout=10) as r:
        payload=json.loads(r.read(3000000).decode("utf-8"))
    data=payload.get("data") if isinstance(payload,dict) else {}
    items=data.get("items") if isinstance(data,dict) else []
    print("INDEX_CHECK",label,"COUNT",len(items) if isinstance(items,list) else -1)
print("INDEX_CHECK_COMPLETE CALLS=2")
