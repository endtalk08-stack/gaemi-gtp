import json,ssl,time
from urllib.request import Request,urlopen
ctx=ssl._create_unverified_context()
for route in ("/market/us-industry-etf-quotes","/market/us-etf-quotes","/market/us-industries?include_stocks=1&view=heatmap","/market/trading-value?market=us"):
 try:
  with urlopen(Request("https://127.0.0.1"+route),timeout=10,context=ctx) as r: d=json.load(r)
  rows=d.get("etf_quotes",[]) if "industries?" in route else d.get("items",[])
  print("LOCAL",route,"ok",d.get("ok"),"count",len(rows),"captured",d.get("captured_at"),flush=True)
  for x in rows[:20]:
   t=x.get("received_at_ms")
   print("RATE",x.get("symbol"),x.get("price"),x.get("change_pct"),"stale",x.get("stale"),"age_s",round(time.time()-t/1000) if isinstance(t,(int,float)) else None,"ref",x.get("reference_close_date"),flush=True)
 except Exception as e: print("ERROR",route,type(e).__name__,str(e)[:140],flush=True)
