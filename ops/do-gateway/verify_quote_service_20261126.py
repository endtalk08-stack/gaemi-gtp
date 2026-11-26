"""Read-only final check: deployed quote-service file hashes and live endpoint values."""
import hashlib
import json
import pathlib
import ssl
import time
import urllib.request

FILES = ("backend/kiwoom_us_top20_api.py", "backend/kiwoom_us_live_prices.py",
         "backend/us_quote_change.py", "backend/providers/kiwoom_us_industries.py",
         "backend/providers/kiwoom_us_quotes.py")
UNITS = ("gaemigtp-kiwoom-us-top20-api.service", "gaemigtp-kiwoom-us-top20-https.service")


def blob(path):
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def get(path):
    req = urllib.request.Request("https://127.0.0.1" + path, headers={
        "Origin": "https://gaemigtp-main.pages.dev", "Accept": "application/json"})
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    started = time.time()
    with opener.open(req, timeout=60) as resp:
        return json.load(resp), time.time() - started


def main():
    for name in FILES:
        print("HASH %s %s" % (blob(pathlib.Path("/opt/gaemigtp-news/app") / name), name), flush=True)
    for unit in UNITS:
        print("HASH %s ops/systemd/%s" % (blob(pathlib.Path("/etc/systemd/system") / unit), unit), flush=True)
    time.sleep(90)   # let the background warmer and close baselines settle after restart
    checks = (
        ("SECTOR_ETF", "/market/us-industry-etf-quotes"),
        ("TOP20", "/market/trading-value?market=us"),
        ("SPY_DIA", "/market/us-etf-quotes"),
    )
    for label, path in checks:
        try:
            data, elapsed = get(path)
            items = [i for i in data.get("items") or [] if isinstance(i, dict)]
            filled = sum(isinstance(i.get("change_pct"), (int, float)) for i in items)
            sample = ", ".join("%s %+.2f%%" % (i["symbol"], i["change_pct"]) for i in items[:3]
                               if isinstance(i.get("change_pct"), (int, float)))
            print("CHECK %s %d/%d rates %.2fs [%s]" % (label, filled, len(items), elapsed, sample), flush=True)
        except Exception as exc:
            print("CHECK %s ERROR %s" % (label, type(exc).__name__), flush=True)
    hold = pathlib.Path("/var/lib/gaemigtp-news/us-regular-last-verified.json")
    print("HOLD_FILE_WRITABLE_DIR=%s" % hold.parent.is_dir(), flush=True)


if __name__ == "__main__":
    main()
