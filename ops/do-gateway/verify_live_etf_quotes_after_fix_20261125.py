import json
from urllib.request import Request,urlopen
url="https://quotes.gaemigtp.com/market/us-industry-etf-quotes"
req=Request(url,headers={"Origin":"https://gaemigtp-main.pages.dev","Accept":"application/json"})
try:
 with urlopen(req,timeout=15) as r:
  data=json.load(r)
  cors=r.headers.get("Access-Control-Allow-Origin")
 rows=data.get("items",[]) if isinstance(data,dict) else []
 valid=[x for x in rows if isinstance(x,dict) and x.get("symbol")]
 live=[x for x in valid if isinstance(x.get("change_pct"),(int,float)) and not x.get("stale")]
 print("PUBLIC_ENDPOINT",url,"ok",data.get("ok"),"count",len(valid),"live_count",len(live),"cors",cors,flush=True)
 for x in valid:
  print("ETF",x.get("symbol"),"change_pct",x.get("change_pct"),"stale",x.get("stale"),"source",x.get("source"),flush=True)
except Exception as e:
 print("PUBLIC_ENDPOINT_ERROR",type(e).__name__,str(e)[:180],flush=True)
