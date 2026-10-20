"""Read-only investigation of missing US stock AI issues. No database/API writes."""
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess

print("AUDIT_UTC", datetime.now(timezone.utc).isoformat(), flush=True)
import os
spec=os.environ.get("NEWS_WORKER_STOCKS","")
fixed=[i.strip() for i in spec.split(",") if i.strip().startswith("미국:")]
print("US_CONFIGURED_FIXED_STOCK_NAMES",repr(fixed),flush=True)
print("FIXED_TOTAL_COUNTS",len([i for i in spec.split(",") if i.strip()]),flush=True)
print("NEWS_WORKER_INTERVAL_SECONDS",os.environ.get("NEWS_WORKER_INTERVAL_SECONDS","default_300"),flush=True)
worker=Path("/opt/gaemigtp-news/app/backend/news_worker.py")
print("WORKER_PRESENT",worker.is_file(),flush=True)
if worker.is_file():
    lines=worker.read_text(encoding="utf-8").splitlines()
    hints=("ranking market=", "apply_worker_ai", "apply_unchanged_worker_ai",
           "process_due_ai_snapshots", "ranking =", "ranking=", "top_stocks",
           "stock_name", "market=미국")
    matches=[(i+1,line.strip()[:160]) for i,line in enumerate(lines)
             if any(token in line for token in hints)]
    print("WORKER_FLOW_LINES",repr(matches[:45]),flush=True)
    print("WORKER_TARGET_ROUTING_BEGIN",flush=True)
    for index in list(range(0,110))+list(range(149,197)):
        if index < len(lines):
            print("WORKER_ROUTING",index+1,lines[index][:210],flush=True)
    print("WORKER_TARGET_ROUTING_END",flush=True)

command=["journalctl","-u","gaemigtp-news.service","--since",
         "2026-10-19 12:00:00 UTC","--no-pager","-o","cat",
         "-g",r"\[news-ai\]|\[news-worker\] ranking"]
try:
    result=subprocess.run(command,capture_output=True,text=True,timeout=20,
                          check=False)
    print("JOURNAL_EXIT",result.returncode,flush=True)
    if result.returncode:
        print("JOURNAL_ERROR_TYPE",
              "permission_denied" if "permission" in result.stderr.lower()
              else "unavailable",flush=True)
    lines=result.stdout.splitlines()
    print("JOURNAL_MATCHED_TOTAL",len(lines),flush=True)
    targets=("메타","아마존","알파벳","코어위브","넷플릭스","마벨",
             "outside_approved_21","ranking market=미국")
    picked=[line[:300] for line in lines if any(t in line for t in targets)]
    print("TARGET_EVENTS_COUNT",len(picked),flush=True)
    for line in picked[-100:]:
        print("TARGET_EVENT",line,flush=True)
    daily=[line[:220] for line in lines if "[news-worker] ranking" in line or
           "[news-ai] skipped" in line]
    print("LAST_RANKING_OR_SKIP",repr(daily[-40:]),flush=True)
except (OSError, subprocess.TimeoutExpired) as exc:
    print("JOURNAL_CHECK_ERROR",type(exc).__name__,flush=True)
print("READONLY_MISSING_US_AI_AUDIT_END",flush=True)
