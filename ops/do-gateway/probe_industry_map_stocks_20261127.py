"""Read-only: list the stocks the live heatmap API currently shows per sector."""
import json
import ssl
import urllib.request


def main():
    req = urllib.request.Request("https://127.0.0.1/market/us-industries?include_stocks=1&view=heatmap",
                                 headers={"Origin": "https://gaemigtp-main.pages.dev", "Accept": "application/json"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    with opener.open(req, timeout=90) as resp:
        data = json.load(resp)
    for row in data.get("items") or []:
        stocks = [{"symbol": s.get("symbol"), "name": s.get("name"), "cap": s.get("market_cap_usd")}
                  for s in (row.get("stocks") or []) if isinstance(s, dict)]
        print("MAP " + json.dumps({"key": row.get("key"), "name": row.get("name"), "stocks": stocks}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
