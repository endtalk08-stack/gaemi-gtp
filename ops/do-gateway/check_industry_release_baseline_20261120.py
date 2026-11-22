"""Check the current quote deployment and its existing Kiwoom industry catalog."""
import hashlib
import json
import math
import ssl
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

APP = Path("/opt/gaemigtp-news/app")
FILES = (
    "backend/providers/kiwoom_us_industries.py",
    "backend/kiwoom_us_live_prices.py",
    "backend/kiwoom_us_top20_api.py",
)
UNITS = ("gaemigtp-news.service", "gaemigtp-kiwoom-us-top20-https.service")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def blob_hash(path):
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def main():
    result = {"files": {name: blob_hash(APP / name) for name in FILES}, "units": {}}
    for name in UNITS:
        status = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, check=False)
        result["units"][name] = status.stdout.strip()

    catalog = {}
    try:
        url = "https://127.0.0.1/market/us-industries?include_stocks=1&view=heatmap"
        request = urllib.request.Request(
            url,
            headers={
                "Origin": "https://gaemigtp-main.pages.dev",
                "Accept": "application/json",
            },
        )
        context = ssl._create_unverified_context()
        client = urllib.request.build_opener(
            NoRedirect(),
            urllib.request.HTTPSHandler(context=context),
        )
        with client.open(request, timeout=30) as response:
            catalog = json.load(response)
            http_status = response.status
        quotes = catalog.get("etf_quotes")
        quote_rows = quotes if isinstance(quotes, list) else []
        expected = {
            "XLK", "XLV", "XLF", "XLY", "XLC", "XLI", "XLP",
            "XLE", "XLU", "XLRE", "XLB", "SOXX", "XBI", "IBIT",
        }
        symbols = {
            str(row.get("symbol") or "").upper()
            for row in quote_rows if isinstance(row, dict)
        }
        invalid = sorted(
            str(row.get("symbol") or "")
            for row in quote_rows
            if not isinstance(row, dict)
            or not isinstance(row.get("change_pct"), (int, float))
            or not math.isfinite(row.get("change_pct"))
            or not isinstance(row.get("received_at_ms"), int)
            or row["received_at_ms"] <= 0
        )
        result["catalog"] = {
            "http_status": http_status,
            "ok": catalog.get("ok") is True,
            "source": catalog.get("source"),
            "fetched_at": catalog.get("fetched_at"),
            "groups": [row.get("key") for row in catalog.get("items", []) if row.get("codes")],
            "etf_quote_count": len(quote_rows),
            "etf_symbols": sorted(symbols),
            "etf_missing_symbols": sorted(expected - symbols),
            "etf_invalid_quote_symbols": invalid,
            "etf_sources": sorted({
                str(row.get("source") or "")
                for row in quote_rows if isinstance(row, dict)
            }),
        }
    except urllib.error.HTTPError as exc:
        result["catalog"] = {"http_status": exc.code}
    except (OSError, ValueError) as exc:
        result["catalog"] = {"error": type(exc).__name__}

    print("INDUSTRY_RELEASE_BASELINE=" + json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
