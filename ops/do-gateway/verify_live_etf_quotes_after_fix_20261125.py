import json
from urllib.request import urlopen
base="https://quotes.gaemigtp.com"
path="/market/us-industry-etf-quotes"
try:
 with urlopen(base+path,timeout=15) as r:
  data=json.load(r)
 rows=data.get("items",[]) if isinstance(data,dict) else []
 valid=[x for x in rows if isinstance(x,dict) and x.get("symbol")]
 live=[x for x in valid if isinstance(x.get("change_pct"),(int,float)) and not x.get("stale")]
 print("PUBLIC_ENDPOINT",base+path,"ok",data.get("ok"),"count",len(valid),"live_count",len(live),flush=True)
 for x in valid:
  print("ETF",x.get("symbol"),"change_pct",x.get("change_pct"),"stale",x.get("stale"),"source",x.get("source"),flush=True)
except Exception as e:
 print("PUBLIC_ENDPOINT_ERROR",type(e).__name__,str(e)[:180],flush=True)
