"""Check the current quote deployment and its existing Kiwoom industry catalog."""
import hashlib
import json
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
        client = urllib.request.build_opener(NoRedirect())
        with client.open("https://quotes.gaemigtp.com/market/us-industries", timeout=15) as response:
            catalog = json.load(response)
        result["catalog"] = {
            "ok": catalog.get("ok") is True,
            "source": catalog.get("source"),
            "fetched_at": catalog.get("fetched_at"),
            "groups": [row.get("key") for row in catalog.get("items", []) if row.get("codes")],
            "media_370": any(
                str(row.get("code")) == "370"
                for row in catalog.get("unmatched_official_industries", [])
            ),
        }
    except urllib.error.HTTPError as exc:
        result["catalog"] = {"http_status": exc.code}
    except (OSError, ValueError) as exc:
        result["catalog"] = {"error": type(exc).__name__}

    print("INDUSTRY_RELEASE_BASELINE=" + json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
