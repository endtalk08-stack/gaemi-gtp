import json, ssl, sys, urllib.request
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend import kiwoom_us_top20_api as api

ctx = ssl._create_unverified_context()
def get(path):
    with urllib.request.urlopen("https://127.0.0.1" + path, context=ctx, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))

health = get("/health")
assert health.get("ok") is True, "https_health_failed"
heatmap = get("/market/us-industries?include_stocks=1&view=heatmap")
assert heatmap.get("ok") is True, "industry_endpoint_failed"
items = heatmap.get("items") or []
assert len(items) == 16, "industry_count_mismatch"
stock_rows = [stock for sector in items for stock in (sector.get("stocks") or [])]
rates = [row for row in stock_rows if type(row.get("change_pct")) in (int, float)]
saved = api._us_close_read_disk()
recovered = []
for symbol in (saved.get("items") or {}):
    quote = api._us_close_get(symbol, exchange=api._CLOSE_EXCHANGES.get(symbol))
    if quote:
        recovered.append(symbol)
print("HTTPS_HEALTH=PASS")
print("INDUSTRY_HEATMAP=PASS sectors=%d stocks=%d percentage_values=%d" % (len(items), len(stock_rows), len(rates)))
print("PERSISTED_RECORDS=%d RESTORED_VALID_QUOTES=%d" % (len(saved.get("items") or {}), len(recovered)))
print("RESTORED_SYMBOLS=" + ",".join(sorted(recovered)[:20]))
if not recovered:
    raise SystemExit("no_valid_persisted_quote_restored")
