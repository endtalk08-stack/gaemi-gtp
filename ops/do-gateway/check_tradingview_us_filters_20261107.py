import os, json, urllib.request, urllib.parse

key=os.environ.get("TRADINGVIEW_API_KEY","").strip()
if not key:
    raise SystemExit("MISSING_KEY")

def fetch(category, params):
    url="https://api.tradingviewapi.com/api/news/"+category
    if params:
        url += "?" + urllib.parse.urlencode(params)
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
    return items

for cat in ("economic","futures"):
    base=fetch(cat,{"lang":"ko"})
    us=fetch(cat,{"lang":"ko","market_country":"US"})
    print("CATEGORY",cat,"BASE",len(base),"US",len(us))
    print("BASE_SAMPLE")
    for x in base[:10]:
        print("-",str(x.get("title") or "")[:160])
    print("US_SAMPLE")
    for x in us[:10]:
        print("-",str(x.get("title") or "")[:160])
    base_ids={str(x.get("id") or "") for x in base if x.get("id")}
    us_ids={str(x.get("id") or "") for x in us if x.get("id")}
    print("SAME_IDS",len(base_ids & us_ids),"US_ONLY",len(us_ids-base_ids),"BASE_ONLY",len(base_ids-us_ids))
    print("---")
print("US_FILTER_CHECK_COMPLETE CALLS=4")
