"""Read-only cached excerpt and rights distribution audit; no external requests."""
import json
from collections import Counter
from pathlib import Path
path=Path("/var/lib/gaemigtp-news/tradingview-news-bundle.json")
if not path.is_file() or path.is_symlink(): raise SystemExit("CACHE_NOT_FOUND")
items=json.loads(path.read_text(encoding="utf-8")).get("items",[])
all_counts=Counter()
excerpt_counts=Counter()
for row in items:
    if not isinstance(row,dict):continue
    provider=row.get("provider") or {}
    name=provider.get("name","unknown") if isinstance(provider,dict) else str(provider)
    k=(str(row.get("permission") or "unspecified"),str(row.get("detail_permission") or "unspecified"),str(row.get("paywall") or "unspecified"),str(name))
    all_counts[k]+=1
    if row.get("shortDescription") or row.get("detail_description"):
        excerpt_counts[k]+=1
print("ALL_RIGHTS_GROUPS",json.dumps([{"rights":list(k),"count":v} for k,v in all_counts.items()],ensure_ascii=False),flush=True)
print("EXCERPT_RIGHTS_GROUPS",json.dumps([{"rights":list(k),"count":v} for k,v in excerpt_counts.items()],ensure_ascii=False),flush=True)
print("EXCERPT_COUNT",sum(excerpt_counts.values()),flush=True)
