import json,ssl
from urllib.request import urlopen
ctx=ssl._create_unverified_context()
for path in ("/market/us-industry-etf-quotes","/market/us-industries?include_stocks=1&view=heatmap"):
 try:
  with urlopen("https://127.0.0.1"+path,timeout=12,context=ctx) as r:
   data=json.load(r)
  rows=data.get("items",[]) if path.startswith("/market/us-industry") and path.endswith("quotes") else data.get("etf_quotes",[])
  if not rows and isinstance(data.get("items"),list):
   rows=data["items"]
  valid=[x for x in rows if isinstance(x,dict) and x.get("symbol")]
  live=[x for x in valid if x.get("change_pct") is not None and not x.get("stale")]
  print("ENDPOINT",path,"ok",data.get("ok"),"etf_count",len(valid),"live_count",len(live),flush=True)
  for x in valid:
   print("ETF",x.get("symbol"),"price",x.get("price"),"change_pct",x.get("change_pct"),"stale",x.get("stale"),"source",x.get("source"),flush=True)
 except Exception as e:
  print("ENDPOINT_ERROR",path,type(e).__name__,str(e)[:120],flush=True)
