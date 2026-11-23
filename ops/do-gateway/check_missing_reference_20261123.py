"""Read-only comparison of missing sector and ranking close sources."""
import datetime as dt
import json, ssl, sys
from urllib.request import urlopen
sys.path.insert(0, '/opt/gaemigtp-news/app')
from backend import us_quote_change as baseline
ctx=ssl._create_unverified_context()
def get(path):
    with urlopen("https://127.0.0.1"+path,timeout=40,context=ctx) as response:
        return json.load(response)
data=get("/market/us-industries?include_stocks=1&view=heatmap")
rows={s['symbol']:s for sector in data.get('items',[]) for s in sector.get('stocks',[]) if s.get('symbol')}
missing=sorted(s for s,x in rows.items() if not isinstance(x.get('change_pct'),(int,float)))
print("SECTOR_SYMBOLS",len(rows),"MISSING",len(missing),missing,flush=True)
print("MISSING_PRICE_PRESENT",sum(isinstance(rows[s].get('price'),(int,float)) for s in missing),flush=True)
print("MISSING_PRICE_SAMPLE",[(s,rows[s].get('price'),rows[s].get('exchange')) for s in missing[:12]],flush=True)
top=get("/market/trading-value?market=us")
print("TOP20_MISSING",[(s.get('symbol'),s.get('price'),s.get('exchange')) for s in top.get('items',[]) if not isinstance(s.get('change_pct'),(int,float))],flush=True)
for symbol,exchange in [('WMT','NY'),('DUK','NY'),('XOM','NY'),('BRK.B','NY'),('COST','ND')]:
    try: print("LOOKUP",symbol,baseline._lookup(symbol,exchange,dt.date(2026,11,22),False),flush=True)
    except Exception as e: print("LOOKUP_ERROR",symbol,type(e).__name__,flush=True)
