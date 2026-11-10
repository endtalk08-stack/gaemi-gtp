"""Collect Kiwoom usa20540 US trading-value Top 20 into DigitalOcean local snapshot only.

No Neon, Render, AI, or news collection. Existing local ranking and identity handoff remain intact.
"""
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

from backend.providers.kiwoom_us_rankings import fetch_us_trading_value_top


def _write_local_news_top20(rows, captured_at, *, target_path=None):
    """Atomic one-server handoff of already fetched Kiwoom ranks and identities.

    This local handoff does not call Neon or Render.
    """
    from pathlib import Path
    import tempfile
    from backend.services.us_top20_rotation import normalize_ranking
    from backend.kiwoom_us_identity_sync import identity_from_kiwoom

    path = Path(target_path) if target_path is not None else Path(
        "/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
    if not path.parent.is_dir() or path.is_symlink():
        raise RuntimeError("unsafe_local_ranking_path")
    normalized = normalize_ranking([
        {"rank": row["rank"], "symbol": row["symbol"], "name": row["name"]}
        for row in rows
    ])
    source_rows = {row["symbol"]: row for row in rows}
    items=[]
    for row in normalized:
        matched=identity_from_kiwoom(row["name"], row["symbol"])
        if matched is None:
            raise ValueError("unmatched_kiwoom_identity")
        items.append({
            **row,
            "exchange": source_rows[row["symbol"]]["exchange"],
            "company_key": matched["company_key"],
            "news_name": matched["news_name"],
            "identity_status": matched["status"],
            # Preserve the values already returned by usa20540 for the
            # DigitalOcean-local TOP20 API; no extra market or DB read.
            "price": source_rows[row["symbol"]]["price"],
            "change_pct": source_rows[row["symbol"]]["change_pct"],
            "trading_value": source_rows[row["symbol"]]["trading_value"],
            "volume": source_rows[row["symbol"]]["volume"],
        })
    data={"schema_version": 1, "source": "kiwoom",
          "market": "US", "rank_type": "trading_value",
          "captured_at": captured_at.isoformat(), "items": items}
    temp_name=None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(path.parent),
            prefix=".kiwoom-news-top20-", delete=False
        ) as handle:
            temp_name=handle.name
            os.fchmod(handle.fileno(), 0o600)
            json.dump(data,handle,ensure_ascii=False,separators=(",",":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name,path)
    finally:
        if temp_name is not None and os.path.exists(temp_name):
            os.unlink(temp_name)

def main():
    import sys
    from pathlib import Path
    if len(sys.argv) > 1:
        raise ValueError("unsupported_collector_argument")

    ny = dt.datetime.now(ZoneInfo("America/New_York"))
    in_session = (ny.weekday() < 4 or
                  (ny.weekday() == 4 and ny.time() < dt.time(20, 0)) or
                  (ny.weekday() == 6 and ny.time() >= dt.time(20, 0)))
    # Off-session, preserve the last valid local Top20 instead of querying a DB.
    if not in_session:
        local = Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
        if local.is_file() and not local.is_symlink():
            print("KIWOOM_US_VALUE_SKIP=outside_us_extended_session", flush=True)
            return 0

    rows = fetch_us_trading_value_top(limit=20)
    if len(rows) != 20 or [row["rank"] for row in rows] != list(range(1, 21)):
        print("KIWOOM_US_VALUE_ERROR=incomplete_source_rows", flush=True)
        return 3

    captured = dt.datetime.now(dt.timezone.utc)
    _write_local_news_top20(rows, captured)
    print("KIWOOM_US_LOCAL_TOP20_UPDATED=20", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
