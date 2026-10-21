"""Read-only inspection: actual Korean popular ordering and deployed worker rank scheduler."""
import sys, inspect, subprocess, json
from pathlib import Path
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.providers.market_price import fetch_kr_popular_ranking_raw
from backend.services.market_rankings import _normalize_kr_stock_rows

raw=fetch_kr_popular_ranking_raw(limit=20)
if raw is None:
 print("RANK_SOURCE_UNAVAILABLE",flush=True)
else:
 rows=_normalize_kr_stock_rows(raw,20)
 print("POPULAR_RANK_ITEMS="+str(len(rows))+" shape="+str(list(raw.keys())),flush=True)
 for row in rows[:20]:
  print("POPULAR "+json.dumps({"rank":row["rank"],"name":row["name"],
    "symbol":row["symbol"],"pct":row["change_pct"]},ensure_ascii=False),flush=True)

s=subprocess.run(["systemctl","show","gaemigtp-news.service","--property=ExecStart","--property=ActiveState","--property=SubState","--property=FragmentPath"],capture_output=True,text=True,timeout=8)
for line in s.stdout.splitlines():
 print("UNIT "+line[:400],flush=True)
app=Path("/opt/gaemigtp-news/app")
for p in app.rglob("*.py"):
 if any(part in {".venv","venv",".git","__pycache__"} for part in p.parts):continue
 if len(p.parts)>len(app.parts)+4:continue
 try: data=p.read_text(errors="replace")
 except (OSError,UnicodeError):continue
 if "def next_ranked_stock" not in data and 'state["ranked"]' not in data:continue
 lines=data.splitlines()
 print("RANK_WORKER_FILE "+str(p.relative_to(app))+" lines="+str(len(lines)),flush=True)
 for i,line in enumerate(lines):
  if ("def next_ranked_stock" in line or "state[\"ranked\"]" in line or "ranked_by_feed" in line or "sleep(" in line):
   print("RANK_WORKER_LINE "+str(i+1)+" "+line[:240],flush=True)
print("READ_ONLY_POPULAR_QUEUE_INSPECTION_DONE",flush=True)
