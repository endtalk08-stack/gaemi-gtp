"""Read-only probe: live TOP20 trading-value API percentages and ranking file metadata."""
import json
import pathlib
import ssl
import urllib.request


def main():
    try:
        raw = json.loads(pathlib.Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json").read_text())
        rows = raw.get("items") or []
        print("FILE captured_at=%s rows=%d file_pct_nonnull=%d" % (
            raw.get("captured_at"), len(rows),
            sum(isinstance(r, dict) and r.get("change_pct") is not None for r in rows)), flush=True)
        for r in rows[:5]:
            print("FILE_ROW %s price=%s pct=%s exch=%s" % (r.get("symbol"), r.get("price"),
                  r.get("change_pct"), r.get("exchange")), flush=True)
    except Exception as exc:
        print("FILE_ERROR=" + type(exc).__name__, flush=True)
    req = urllib.request.Request("https://127.0.0.1/market/trading-value?market=us",
                                 headers={"Origin": "https://gaemigtp-main.pages.dev",
                                          "Accept": "application/json"})
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    with opener.open(req, timeout=60) as resp:
        data = json.load(resp)
    items = data.get("items") or []
    print("API ok=%s keys=%s items=%d pct_nonnull=%d" % (
        data.get("ok"), sorted(k for k in data if k != "items"), len(items),
        sum(isinstance(i, dict) and i.get("change_pct") is not None for i in items)), flush=True)
    for i in items[:20]:
        print("API_ROW %s price=%s pct=%s ref=%s" % (i.get("symbol"), i.get("price"),
              i.get("change_pct"), i.get("reference_close_date")), flush=True)


if __name__ == "__main__":
    main()
