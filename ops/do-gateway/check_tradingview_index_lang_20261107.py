import os, json, urllib.request, urllib.parse

key=os.environ.get("TRADINGVIEW_API_KEY","").strip()
if not key:
    raise SystemExit("MISSING_KEY")

base="https://api.tradingviewapi.com/api/news/index"
for lang in ("en","ja"):
    url=base+"?"+urllib.parse.urlencode({"lang":lang})
    req=urllib.request.Request(url,headers={
        "Authorization":"Bearer "+key,
        "Accept":"application/json",
        "User-Agent":"gaemiGTP-index-lang-check/1.0",
    })
    with urllib.request.urlopen(req,timeout=12) as r:
        payload=json.loads(r.read(3_000_000).decode("utf-8"))
    data=payload.get("data") if isinstance(payload,dict) else {}
    items=data.get("items") if isinstance(data,dict) else []
    if not isinstance(items,list): items=[]
    print("INDEX_LANG",lang,"COUNT",len(items))
    if items:
        print("SAMPLE",lang,"|",str(items[0].get("title") or "")[:180])
print("INDEX_LANG_CHECK_COMPLETE CALLS=2")
