"""Read-only: check whether the materials (소재) sector tile's 0% reading
is a stale/stuck ETF tick, or a real (if initially surprising) divergence
from its top-3 listed stocks."""
import json
import ssl
from urllib.request import urlopen

ctx = ssl._create_unverified_context()


def get(path):
    with urlopen("https://127.0.0.1" + path, timeout=40, context=ctx) as response:
        return json.load(response)


industry = get("/market/us-industries?include_stocks=1&view=heatmap")
items = industry.get("items") or []
materials = next((i for i in items if i.get("key") == "materials"), None)
print("MATERIALS_ITEM", json.dumps(materials)[:1500], flush=True)

etf_quotes = industry.get("etf_quotes") or []
xlb = next((q for q in etf_quotes if q.get("symbol") == "XLB"), None)
print("XLB_QUOTE", xlb, flush=True)
