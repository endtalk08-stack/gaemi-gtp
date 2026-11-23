"""Read-only: dump raw QQQ/SPY/DIA quotes as the public API currently returns them,
to check whether their change_pct values reflect the same reference session."""
import json
import ssl
from urllib.request import urlopen

ctx = ssl._create_unverified_context()


def get(path):
    with urlopen("https://127.0.0.1" + path, timeout=40, context=ctx) as response:
        return json.load(response)


widget = get("/market/us-etf-quotes")
print("WIDGET_RAW", json.dumps(widget), flush=True)

industry = get("/market/us-industries?include_stocks=1&view=heatmap")
etf_quotes = industry.get("etf_quotes") or []
by_symbol = {q.get("symbol"): q for q in etf_quotes}
for sym in ("XLK", "XLY", "XLC", "XLI", "XLB", "XLRE", "SOXX"):
    print("ETF", sym, by_symbol.get(sym), flush=True)
