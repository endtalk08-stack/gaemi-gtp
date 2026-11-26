import json, ssl, urllib.request
ctx = ssl._create_unverified_context()
def get(url, tls=False):
    with urllib.request.urlopen(url, context=ctx if tls else None, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
health = get("http://127.0.0.1:8765/health")
top = get("http://127.0.0.1:8765/market/trading-value?market=us")
assert health.get("ok") is True, "plain_health_failed"
rows = top.get("items") or []
assert top.get("ok") is True and len(rows) == 20, "top20_endpoint_invalid"
top_rates = [x for x in rows if type(x.get("change_pct")) in (int, float)]
industry = get("https://127.0.0.1/market/us-industries?include_stocks=1&view=heatmap", tls=True)
assert industry.get("ok") is True, "industry_endpoint_invalid"
sectors = industry.get("items") or []
stocks = [x for sector in sectors for x in (sector.get("stocks") or [])]
industry_rates = [x for x in stocks if type(x.get("change_pct")) in (int, float)]
print("PLAIN_HEALTH=PASS", flush=True)
print("TOP20=PASS rows=%d numeric_percentages=%d" % (len(rows), len(top_rates)), flush=True)
print("HTTPS_INDUSTRY=PASS sectors=%d stocks=%d numeric_percentages=%d" %
      (len(sectors), len(stocks), len(industry_rates)), flush=True)
