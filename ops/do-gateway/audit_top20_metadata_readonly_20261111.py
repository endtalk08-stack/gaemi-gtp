"""Read-only operational readiness for US TOP20 metadata persistence."""
import json
import re
import subprocess
from pathlib import Path

UNITS = (
    "gaemigtp-kiwoom-us-value.timer",
    "gaemigtp-kiwoom-us-top20-api.service",
    "gaemigtp-kiwoom-us-daily.timer",
    "gaemigtp-kiwoom-us-daily.service",
)
for unit in UNITS:
    for field in ("ActiveState", "UnitFileState"):
        result = subprocess.run(
            ("systemctl", "show", "--property=" + field, "--value", unit),
            capture_output=True, text=True, timeout=5,
        )
        print("UNIT", unit, field, (result.stdout.strip() or "unknown")[:40],
              flush=True)

snapshot = Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
try:
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    rows = data.get("items") if isinstance(data, dict) else None
    assert isinstance(rows, list) and len(rows) == 20
    print("SNAPSHOT_ROWS", len(rows), flush=True)
    print("SNAPSHOT_TURNOVER_VALID",
          sum(isinstance(r.get("trading_value"), (int, float))
              and not isinstance(r.get("trading_value"), bool)
              and r["trading_value"] >= 0 for r in rows), flush=True)
    print("SNAPSHOT_INDUSTRY_PRESENT",
          sum(isinstance(r.get("industry"), str) and bool(r.get("industry").strip())
              for r in rows), flush=True)
    print("SNAPSHOT_EXCHANGE_PRESENT",
          sum(bool(r.get("exchange")) for r in rows), flush=True)
    print("SNAPSHOT_CAPTURED", str(data.get("captured_at"))[:40], flush=True)
except (OSError, ValueError, TypeError, AssertionError) as exc:
    print("SNAPSHOT_ERROR", type(exc).__name__, flush=True)

for path in (
    Path("/etc/gaemigtp/news-worker.env"),
    Path("/var/lib/gaemigtp-news/r2.env"),
):
    if not path.is_file():
        print("ENV_FILE", path.name, "absent", flush=True)
        continue
    try:
        raw = path.read_text(encoding="utf-8")
        found = set()
        for line in raw.splitlines():
            match = re.match(r"^(?:export\\s+)?([A-Z][A-Z0-9_]*)\\s*=", line.strip())
            if match:
                found.add(match.group(1))
        for name in ("NEWS_DATABASE_URL", "DATABASE_URL", "R2_ACCESS_KEY_ID",
                     "R2_SECRET_ACCESS_KEY", "GAEMIGTP_NEWS_STORAGE"):
            print("ENV_KEY_PRESENT", path.name, name, name in found, flush=True)
    except OSError as exc:
        print("ENV_FILE", path.name, type(exc).__name__, flush=True)
