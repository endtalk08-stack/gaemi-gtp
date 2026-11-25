"""Read-only: the user is comparing the current live sector/industry map
against a proposed hand-curated "theme ETF" heatmap, and asked whether the
current sector->stock composition is well-formed. Pull the actual live
/market/us-industries?include_stocks=1&view=heatmap response straight from
the service over localhost (the public domain errored on a direct fetch)
so the full list of sectors and their assigned stocks can be reviewed,
rather than guessing from a partial screenshot."""
import json
import ssl
from urllib.request import urlopen

ctx = ssl._create_unverified_context()
with urlopen("https://127.0.0.1/market/us-industries?include_stocks=1&view=heatmap",
             timeout=40, context=ctx) as response:
    data = json.load(response)

items = data.get("items", [])
print("SECTOR_COUNT", len(items), flush=True)
for item in items:
    stocks = item.get("stocks") or []
    print("KEY=" + str(item.get("key")), "NAME=" + str(item.get("name")),
          "HIDE_CHANGE=" + str(item.get("hideChange")),
          "STOCK_COUNT=" + str(len(stocks)),
          "STOCKS=" + json.dumps([(s.get("symbol"), s.get("name")) for s in stocks],
                                 ensure_ascii=False),
          flush=True)
