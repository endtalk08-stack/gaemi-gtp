"""Read-only audit of US live rates and regular-close references, no mutations."""
import datetime as dt
import json
import ssl
import time
from zoneinfo import ZoneInfo
from urllib.request import urlopen
from backend import us_quote_change as changes

print("AUDIT_AT_UTC", dt.datetime.now(dt.timezone.utc).isoformat(), flush=True)
print("AUDIT_AT_NY", dt.datetime.now(ZoneInfo("America/New_York")).isoformat(), flush=True)
ctx=ssl._create_unverified_context()
def check(path, timeout):
    t=time.monotonic()
    try:
        with urlopen("https://127.0.0.1"+path,context=ctx,timeout=timeout) as r:
            data=json.load(r)
        print("API",path,"elapsed",round(time.monotonic()-t,2),"ok",data.get("ok"),flush=True)
        return data
    except Exception as e:
        print("API_ERROR",path,type(e).__name__,str(e)[:140],"elapsed",round(time.monotonic()-t,2),flush=True)
        return {}
def compact(q):
    return {k:q.get(k) for k in ("symbol","price","change_pct","reference_close_date","source","stale","received_at_ms") if k in q}
snapshot=check("/market/us-etf-quotes",25)
print("WIDGET_QUOTES", [compact(q) for q in snapshot.get("items",[]) if q.get("symbol") in ("SPY","DIA")],flush=True)
top=check("/market/trading-value?market=us",12)
print("TOP20_STATUS",len(top.get("items",[])),top.get("captured_at"),
  [(x.get("symbol"),x.get("change_pct")) for x in top.get("items",[]) if x.get("symbol") in ("NVDA","SPY","AAPL")],flush=True)
mapdata=check("/market/us-industries?include_stocks=1&view=heatmap",40)
etfs=mapdata.get("etf_quotes") or []
print("SECTOR_ETF_STATUS",len(etfs),sum(type(q.get("change_pct")) in (int,float) for q in etfs),
 [(q.get("symbol"),q.get("change_pct"),q.get("source")) for q in etfs if q.get("symbol") in ("XLK","XLV","SOXX","IBIT","XBI")],flush=True)
stockrows=[x for sector in mapdata.get("items",[]) for x in sector.get("stocks",[])]
print("SECTOR_STOCK_STATUS",len(stockrows),sum(type(q.get("change_pct")) in (int,float) for q in stockrows),
 [(q.get("symbol"),q.get("change_pct")) for q in stockrows if q.get("symbol") in ("NVDA","MSFT","AAPL","COIN")],flush=True)
for symbol,exchange in [("DIA","NY"),("XLK","NY"),("IBIT","ND")]:
    t=time.monotonic()
    try:
        result=changes._lookup(symbol,exchange,dt.date(2026,11,22),False)
        print("YAHOO_CLOSE",symbol,result,"elapsed",round(time.monotonic()-t,2),flush=True)
    except Exception as e:
        print("YAHOO_ERROR",symbol,type(e).__name__,"elapsed",round(time.monotonic()-t,2),flush=True)
