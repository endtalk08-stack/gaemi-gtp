"""Read only file hashes and targeted source layout before AI directional material changes."""
import ast,subprocess
from pathlib import Path
base=Path("/opt/gaemigtp-news/app")
files=("ops/staged_daily_groq_issues.py","ops/staged_ai_sequential_batch.py",
       "ops/staged_ai_issue_store.py","ops/staged_ai_issue_display_adapter.py",
       "ops/staged_ai_snapshot_integration.py","ops/staged_auto_ai_daily.py")
for file in files:
 p=base/file
 if not p.is_file() or p.is_symlink(): raise SystemExit("MISSING "+file)
 data=p.read_text(encoding="utf8")
 ast.parse(data,filename=file)
 sha=subprocess.check_output(["git","hash-object",str(p)],text=True).strip()
 print("FILE_HASH",file,sha,len(data.splitlines()),flush=True)
 for lineno,line in enumerate(data.splitlines(),1):
  if line.startswith(("def analyze_news","def parse_issues","def to_issue_briefs","def with_ai_issue_briefs",
    "def run_stock_batch","def save_ai_issues","def read_issue_sources","def apply_worker_ai",
    "def process_due_ai_snapshots")) or "parse_issues(content)" in line or "parse_analysis(content)" in line or "_RECONCILE_DISPLAY_SQL" in line:
   print("SOURCE_MARKER",file,lineno,line[:110],flush=True)
print("MATERIALS_BASELINE_OK",flush=True)
