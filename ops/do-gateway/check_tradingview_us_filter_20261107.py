import os, json, urllib.request, urllib.parse

key=os.environ.get("TRADINGVIEW_API_KEY","").strip()
if not key:
    raise SystemExit("MISSING_KEY")

base="https://api.tradingviewapi.com/api/news"
for category in ("economic","futures"):
    params={"lang":"ko","market_country":"US"}
    url=base+"/"+category+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={
        "Authorization":"Bearer "+key,
        "Accept":"application/json",
        "User-Agent":"gaemiGTP-us-filter-check/1.0",
    })
    with urllib.request.urlopen(req,timeout=12) as r:
        payload=json.loads(r.read(3_000_000).decode("utf-8"))
    data=payload.get("data") if isinstance(payload,dict) else {}
    items=data.get("items") if isinstance(data,dict) else []
    if not isinstance(items,list): items=[]
    print("CATEGORY",category,"COUNT",len(items))
    for x in items[:20]:
        print("TITLE",category,"|",str(x.get("title") or "")[:180])
print("US_FILTER_CHECK_COMPLETE CALLS=2")
