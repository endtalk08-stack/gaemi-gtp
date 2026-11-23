"""Publish local Kiwoom Top20 instrument metadata to R2 only.

The local ranking JSON is the source. Preserve existing industry labels from
the prior R2 catalog where a current Kiwoom row does not carry one.
"""
from __future__ import annotations
import datetime as dt
import json
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.kiwoom_us_identity_sync import identity_from_kiwoom
from backend.services.r2_news_uploader import read_r2_json, upload_file

NY = ZoneInfo("America/New_York")
R2_OBJECT = "stocks/us/instruments.json"
RANKING_FILE = Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")


def _read_local_ranking():
    if RANKING_FILE.is_symlink() or not RANKING_FILE.is_file():
        raise RuntimeError("local_top20_missing")
    data = json.loads(RANKING_FILE.read_text(encoding="utf-8"))
    rows = data.get("items") if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) != 20:
        raise RuntimeError("local_top20_incomplete")
    if [row.get("rank") for row in rows] != list(range(1, 21)):
        raise RuntimeError("local_top20_invalid_rank")
    captured = dt.datetime.fromisoformat(str(data.get("captured_at") or "").replace("Z", "+00:00"))
    if captured.tzinfo is None:
        raise RuntimeError("local_top20_missing_timezone")
    return data, rows


def sync_once_after_close(*, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    ny = now.astimezone(NY)
    if ny.weekday() > 4 or ny.time() < dt.time(16, 15):
        return "skipped_outside_close"
    data, rows = _read_local_ranking()
    captured = dt.datetime.fromisoformat(str(data["captured_at"]).replace("Z", "+00:00")).astimezone(NY)
    if captured.date() != ny.date() or captured.time() < dt.time(16):
        return "skipped_stale_or_incomplete_ranking"
    old = read_r2_json(R2_OBJECT) or {}
    old_items = old.get("items") if isinstance(old, dict) else []
    old_industry = {str(row.get("symbol") or "").upper(): row.get("industry")
                    for row in old_items if isinstance(row, dict)}
    items = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        name = str(row.get("name") or "").strip()
        exchange = str(row.get("exchange") or "").strip().upper()
        if not symbol or not name or exchange not in ("ND", "NY", "NA"):
            raise RuntimeError("local_top20_invalid_identity")
        identity = identity_from_kiwoom(name, symbol)
        if identity is None:
            raise RuntimeError("local_top20_identity_unmatched")
        items.append({
            "symbol": symbol, "name": name, "exchange": exchange,
            "company_key": identity["company_key"],
            "news_name": identity["news_name"],
            "identity_status": identity["status"],
            "industry": old_industry.get(symbol) or row.get("industry") or "",
        })
    payload = {"schema_version": 1, "source": "kiwoom", "market": "US",
               "generated_at": now.isoformat(), "items": items}
    filename = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         suffix=".json", delete=False) as handle:
            filename = handle.name
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        if not upload_file(Path(filename), object_key=R2_OBJECT):
            raise RuntimeError("r2_instrument_upload_failed")
        return "r2_instruments_updated_20"
    finally:
        if filename and Path(filename).exists():
            Path(filename).unlink()
