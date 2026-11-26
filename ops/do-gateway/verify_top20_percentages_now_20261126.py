import json, ssl, sys, urllib.request
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend import kiwoom_us_top20_api as api
ctx=ssl._create_unverified_context()
def read(url, tls=False):
    with urllib.request.urlopen(url, context=ctx if tls else None, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))
local=api.read_top20()
for label, data in (
    ("MODULE", local),
    ("PLAIN", read("http://127.0.0.1:8765/market/trading-value?market=us")),
    ("HTTPS", read("https://127.0.0.1/market/trading-value?market=us", True)),
):
    rows=data.get("items") or []
    rates=[x for x in rows if type(x.get("change_pct")) in (int,float)]
    print("%s rows=%d numeric_percentages=%d sample=%s" %
          (label,len(rows),len(rates),[(x.get("symbol"),x.get("change_pct")) for x in rows[:3]]), flush=True)
    assert data.get("ok") is True and len(rows)==20, label+"_rows_invalid"
    assert len(rates)==20, label+"_percentages_missing"
