import json, os, ssl, urllib.request
from pathlib import Path

ctx = ssl._create_unverified_context()
checks = [
    ("https", "https://127.0.0.1/health"),
    ("https_top20", "https://127.0.0.1/market/trading-value?market=us"),
    ("http_top20", "http://127.0.0.1:8765/market/trading-value?market=us"),
    ("https_industries", "https://127.0.0.1/market/us-industries?view=heatmap&include_stocks=1"),
]
for name, url in checks:
    try:
        req = urllib.request.Request(url, headers={"Host": "localhost"})
        with urllib.request.urlopen(req, context=ctx if url.startswith("https") else None, timeout=8) as response:
            data = json.load(response)
        items = data.get("items") or []
        if name.endswith("top20"):
            numeric = [x for x in items if type(x.get("change_pct")) in (int, float)]
            print(name + " ok=" + str(data.get("ok")) + " count=" + str(len(items)) +
                  " pct=" + str(len(numeric)) + " sample=" + repr(items[:3]), flush=True)
        elif name == "https_industries":
            stocks = [s for sector in items for s in (sector.get("stocks") or [])]
            numeric = [s for s in stocks if type(s.get("change_pct")) in (int, float)]
            print(name + " ok=" + str(data.get("ok")) + " sectors=" + str(len(items)) +
                  " stocks=" + str(len(stocks)) + " pct=" + str(len(numeric)) +
                  " sample=" + repr(stocks[:3]), flush=True)
        else:
            print(name + " " + repr(data), flush=True)
    except Exception as exc:
        print(name + " ERROR=" + type(exc).__name__ + ":" + str(exc), flush=True)

for name, url in (
    ("public_top20", "https://quotes.gaemigtp.com/market/trading-value?market=us"),
    ("public_industries", "https://quotes.gaemigtp.com/market/us-industries?view=heatmap&include_stocks=1"),
):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "gaemiGTP-health-check"})
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.load(response)
        items = data.get("items") or []
        if name == "public_top20":
            numeric = [x for x in items if type(x.get("change_pct")) in (int, float)]
            print(name + " ok=" + str(data.get("ok")) + " count=" + str(len(items)) +
                  " pct=" + str(len(numeric)), flush=True)
        else:
            stocks = [s for sector in items for s in (sector.get("stocks") or [])]
            numeric = [s for s in stocks if type(s.get("change_pct")) in (int, float)]
            print(name + " ok=" + str(data.get("ok")) + " sectors=" + str(len(items)) +
                  " stocks=" + str(len(stocks)) + " pct=" + str(len(numeric)), flush=True)
    except Exception as exc:
        print(name + " ERROR=" + type(exc).__name__ + ":" + str(exc), flush=True)

for path in (Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json"),
             Path("/var/lib/gaemigtp-news/us-regular-last-verified.json")):
    try:
        st = path.stat()
        print("FILE " + str(path) + " exists=1 size=" + str(st.st_size) +
              " owner=" + str(st.st_uid) + ":" + str(st.st_gid) +
              " mode=" + oct(st.st_mode & 0o777), flush=True)
        if path.name == "us-regular-last-verified.json":
            data = json.loads(path.read_text())
            rows = data.get("items") or {}
            good = [r for r in rows.values() if type(r.get("change_pct")) in (int, float)]
            print("PERSISTED day=" + str(data.get("day")) + " items=" + str(len(rows)) +
                  " pct=" + str(len(good)) + " symbols=" + ",".join(sorted(rows)), flush=True)
    except Exception as exc:
        print("FILE " + str(path) + " ERROR=" + type(exc).__name__ + ":" + str(exc), flush=True)
