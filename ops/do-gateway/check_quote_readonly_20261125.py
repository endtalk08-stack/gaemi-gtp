import json,time
from urllib.request import Request,urlopen
base="https://quotes.gaemigtp.com"
for route in ("/market/us-industry-etf-quotes","/market/us-live-quotes"):
 for origin in ("https://gaemigtp-main.pages.dev","https://pr-160.gaemigtp-main.pages.dev"):
  try:
   with urlopen(Request(base+route,headers={"Origin":origin,"Accept":"application/json","Cache-Control":"no-cache"}),timeout=10) as r:
    d=json.load(r); cors=r.headers.get("Access-Control-Allow-Origin")
   items=d.get("items",[]) if isinstance(d,dict) else []
   print("QUOTE",route,origin,"cors",cors,"ok",d.get("ok"),"count",len(items),flush=True)
   for x in items[:20]:
    if isinstance(x,dict):
     t=x.get("received_at_ms")
     print(x.get("symbol"),x.get("price"),x.get("change_pct"),"stale",x.get("stale"),"age_s",round(time.time()-t/1000) if isinstance(t,(int,float)) else None,"ref",x.get("reference_close_date"),flush=True)
  except Exception as e: print("ERROR",route,origin,type(e).__name__,str(e)[:140],flush=True)
