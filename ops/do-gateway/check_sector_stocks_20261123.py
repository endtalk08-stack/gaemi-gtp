"""Read-only: check why most sector tiles show no top-stock list even though
their change_pct is populated."""
import json
import ssl
from urllib.request import urlopen

ctx = ssl._create_unverified_context()


def get(path):
    with urlopen("https://127.0.0.1" + path, timeout=40, context=ctx) as response:
        return json.load(response)


data = get("/market/us-industries?include_stocks=1&view=heatmap")
items = data.get("items") or []
print("ITEM_COUNT", len(items), flush=True)
for item in items:
    if not isinstance(item, dict):
        continue
    stocks = item.get("stocks")
    print("SECTOR", item.get("key"), "change_pct=", item.get("change_pct"),
          "n_stocks=", len(stocks) if isinstance(stocks, list) else stocks, flush=True)
