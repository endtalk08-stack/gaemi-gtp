import json, ssl, urllib.request
ctx=ssl._create_unverified_context()
def get(url, context=None):
    with urllib.request.urlopen(url, context=context, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))
for label,url,context in (
    ("PLAIN","http://127.0.0.1:8765/market/trading-value?market=us",None),
    ("HTTPS","https://127.0.0.1/market/trading-value?market=us",ctx),
):
    data=get(url,context)
    rows=data.get("items") or []
    rates=[x for x in rows if type(x.get("change_pct")) in (int,float)]
    print("%s rows=%d numeric_percentages=%d sample=%s" %
          (label,len(rows),len(rates),[(x.get("symbol"),x.get("change_pct")) for x in rows[:5]]),flush=True)
