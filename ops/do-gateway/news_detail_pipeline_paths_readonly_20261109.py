"""Locate existing TradingView detail-to-page formatting code, read only."""
from pathlib import Path
root=Path("/opt/gaemigtp-news/app")
patterns=("detail_body","astDescription","detail_description","tradingview-news-page.json","write_snapshot(")
seen=0
for base in (root/"backend",root/"scripts",root/"ops"):
    if not base.is_dir():continue
    for file in base.rglob("*.py"):
        try:
            if file.is_symlink() or file.stat().st_size>600000:continue
            lines=file.read_text(encoding="utf-8").splitlines()
        except Exception:continue
        for idx,line in enumerate(lines,1):
            if any(k in line for k in patterns):
                if any(d in line.lower() for d in ("api_key","api-token","authorization","password","secret")):continue
                print(f"CODE_LOCATION={file.relative_to(root)}:{idx} {line.strip()[:170]}",flush=True)
                seen+=1
                if seen>=85:raise SystemExit(0)
print("MATCH_COUNT="+str(seen),flush=True)
