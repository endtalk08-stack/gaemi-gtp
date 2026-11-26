"""Read-only probe of the QQQ/SPY/DIA market widget endpoints."""
import json
import ssl
import time
import urllib.request


def get(path):
    req = urllib.request.Request("https://127.0.0.1" + path, headers={
        "Origin": "https://gaemigtp-main.pages.dev", "Accept": "application/json"})
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    with opener.open(req, timeout=60) as resp:
        return resp.status, json.load(resp)


def main():
    for attempt in range(3):
        for path in ("/market/us-etf-quotes",):
            try:
                status, data = get(path)
                items = data.get("items") if isinstance(data, dict) and "items" in data else data
                print("T%d %s %s %s" % (attempt, path, status, json.dumps(items)[:600]), flush=True)
            except Exception as exc:
                print("T%d %s ERROR %s" % (attempt, path, type(exc).__name__), flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
