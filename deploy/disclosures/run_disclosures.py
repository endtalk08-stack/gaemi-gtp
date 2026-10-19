"""Run isolated daily DART/SEC collection on DigitalOcean, not on Render.

Supports a one-stock-per-market smoke run before the complete registered set.
The existing gaemigtp-news.service and its schedule are never modified.
"""
import argparse
import json
import os
import sys
from pathlib import Path

APP = Path("/opt/gaemigtp-news/app")
HOME = Path.home()
STAGE = HOME / ".gaemi-disclosures" / "stage"
CREDENTIALS = HOME / ".gaemi-disclosures" / "credentials.json"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=("KR", "US", "all"), default="all")
    parser.add_argument("--smoke", action="store_true", help="One KR and one US stock only")
    parser.add_argument("--cleanup-only", action="store_true", help="Remove expired 24-hour rows only")
    parser.add_argument("--no-ranked", action="store_true", help="Verify mapped stock universe without refreshing rankings")
    args = parser.parse_args(argv)

    if not APP.is_dir() or not STAGE.is_dir():
        raise RuntimeError("disclosure_stage_or_app_missing")
    if CREDENTIALS.is_file():
        if CREDENTIALS.stat().st_mode & 0o077:
            raise RuntimeError("disclosure_credentials_permissions_unsafe")
        data = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
        for name in ("NEWS_DATABASE_URL", "OPENDART_API_KEY", "SEC_USER_AGENT"):
            value = data.get(name, "")
            if isinstance(value, str) and value.strip():
                os.environ[name] = value
    # Read-only one-off tests may use env vars instead of writing secrets to disk.
    required = ("NEWS_DATABASE_URL",) if args.cleanup_only else ("NEWS_DATABASE_URL", "OPENDART_API_KEY")
    for name in required:
        if not os.environ.get(name, "").strip():
            raise RuntimeError("disclosure_credential_missing_" + name)

    os.environ.pop("DISCLOSURE_NEON_READ", None)
    os.environ.pop("DISCLOSURE_NEON_ONLY", None)
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    import backend.providers
    import backend.services
    backend.providers.__path__.insert(0, str(STAGE))
    backend.services.__path__.insert(0, str(STAGE))
    from backend.services import engine
    from backend.services.disclosure_transfer import collect_once, cleanup_expired
    if args.cleanup_only:
        print("DISCLOSURE_EXPIRED_DELETED", cleanup_expired(), flush=True)
        return

    registered = {
        "KR": sorted(engine.DART_STOCK_CORP_CODES),
        "US": sorted(engine.US_CIKS),
    }
    if not args.smoke and not args.no_ranked:
        from backend.services.disclosure_ranked_universe import resolve_universe
        registered = resolve_universe(engine)
    chosen = {
        "KR": ["005930"] if args.smoke else registered["KR"],
        "US": ["AAPL"] if args.smoke else registered["US"],
    }
    failed = []
    for market in ("KR", "US"):
        if args.market not in (market, "all"):
            continue
        for symbol in chosen[market]:
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
    print("DISCLOSURE_COLLECTION_COMPLETE", args.market, flush=True)


if __name__ == "__main__":
    main()
