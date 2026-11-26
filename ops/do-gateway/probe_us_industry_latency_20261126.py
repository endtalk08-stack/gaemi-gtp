"""Read-only latency probe of the live industry endpoints (no writes, no restarts)."""
import json
import ssl
import time
import urllib.request

BASE = "https://127.0.0.1"
PATHS = (
    "/market/us-industry-etf-quotes",
    "/market/us-industries?view=heatmap",
    "/market/us-industries?include_stocks=1&view=heatmap",
)


def get(path):
    req = urllib.request.Request(BASE + path, headers={
        "Origin": "https://gaemigtp-main.pages.dev", "Accept": "application/json",
        "Cache-Control": "no-cache"})
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    started = time.time()
    with opener.open(req, timeout=90) as resp:
        body = resp.read()
    return time.time() - started, len(body)


def main():
    # Let the server caches expire first so we see what a first visitor sees.
    time.sleep(65)
    for rnd in ("cold", "warm"):
        for path in PATHS:
            try:
                elapsed, size = get(path)
                print("LAT %s %-55s %.2fs %dB" % (rnd, path, elapsed, size), flush=True)
            except Exception as exc:
                print("LAT %s %s ERROR %s" % (rnd, path, type(exc).__name__), flush=True)


if __name__ == "__main__":
    main()
