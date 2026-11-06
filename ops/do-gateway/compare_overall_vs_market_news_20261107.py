import os, json, urllib.request, urllib.parse
from pathlib import Path

key=os.environ.get("TRADINGVIEW_API_KEY","").strip()
if not key:
    raise SystemExit("MISSING_KEY")

page=json.loads(Path("/var/lib/gaemigtp-news/tradingview-news-page.json").read_text(encoding="utf-8"))
market=[x for x in page.get("items",[]) if x.get("news_section")=="market"]
market_ids={str(x.get("id")) for x in market if x.get("id") not in (None,"")}
market_titles={str(x.get("title") or "").strip():x for x in market if str(x.get("title") or "").strip()}

url="https://api.tradingviewapi.com/api/news?" + urllib.parse.urlencode({"lang":"ko"})
req=urllib.request.Request(url,headers={
    "Authorization":"Bearer "+key,
    "Accept":"application/json",
    "User-Agent":"gaemiGTP-overlap-check/1.0",
})
with urllib.request.urlopen(req,timeout=12) as r:
    payload=json.loads(r.read(3_000_000).decode("utf-8"))
data=payload.get("data") if isinstance(payload,dict) else {}
items=data.get("items") if isinstance(data,dict) else []
if not isinstance(items,list):
    items=[]

overall_ids={str(x.get("id") or x.get("newsId")) for x in items if isinstance(x,dict) and (x.get("id") or x.get("newsId")) not in (None,"")}
id_overlap=overall_ids & market_ids

title_overlap=[]
for x in items:
    if not isinstance(x,dict):
        continue
    t=str(x.get("title") or "").strip()
    if t and t in market_titles:
        title_overlap.append(t)

print("OVERALL_COUNT",len(items))
print("MARKET_COUNT",len(market))
print("ID_OVERLAP",len(id_overlap))
print("TITLE_EXACT_OVERLAP",len(set(title_overlap)))
if market:
    print("MARKET_OVERLAP_PCT","%.1f"%(100*len(id_overlap)/len(market)))
if items:
    print("OVERALL_OVERLAP_PCT","%.1f"%(100*len(id_overlap)/len(items)))
for x in items:
    if not isinstance(x,dict):
        continue
    i=str(x.get("id") or x.get("newsId") or "")
    if i in id_overlap:
        print("OVERLAP",i,"|",str(x.get("title") or "")[:180])
