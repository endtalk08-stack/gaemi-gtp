"""Isolated, scheduled disclosure collection. Never starts the news worker.

The DigitalOcean deployment installs this file in a restricted staging directory.
It reuses the tested backend, SEC, DART and disclosure_transfer modules; only
news-independent disclosure snapshots are written to Neon.
"""
import json
import os
import sys
from pathlib import Path

APP = Path("/opt/gaemigtp-news/app")
HOME = Path.home()
STAGE = HOME / ".gaemi-disclosures" / "stage"
CREDENTIALS = HOME / ".gaemi-disclosures" / "credentials.json"


def main():
    if not APP.is_dir() or not STAGE.is_dir():
        raise RuntimeError("disclosure_stage_or_app_missing")
    if not CREDENTIALS.is_file():
        raise RuntimeError("disclosure_credentials_missing")
    if CREDENTIALS.stat().st_mode & 0o077:
        raise RuntimeError("disclosure_credentials_permissions_unsafe")
    data = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    for name in ("NEWS_DATABASE_URL", "OPENDART_API_KEY"):
        value = data.get(name, "")
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError("disclosure_credential_missing_" + name)
        os.environ[name] = value
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    import backend.providers
    import backend.services
    backend.providers.__path__.insert(0, str(STAGE))
    backend.services.__path__.insert(0, str(STAGE))
    from backend.services.disclosure_transfer import collect_once
    failed = []
    for market, symbol in (("KR", "005930"), ("US", "AAPL")):
        try:
            result = collect_once(market, symbol)
            print("DISCLOSURE_COLLECT_OK", market, symbol,
                  result["filing_count"], flush=True)
        except Exception as exc:
            failed.append((market, symbol, type(exc).__name__))
            print("DISCLOSURE_COLLECT_ERROR", market, symbol,
                  type(exc).__name__, flush=True)
    if failed:
        raise RuntimeError("disclosure_collection_failed")


if __name__ == "__main__":
    main()
