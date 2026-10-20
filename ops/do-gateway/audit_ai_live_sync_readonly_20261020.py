"""Read-only live worker AI persistence inspection. No DB, network or AI calls."""
from __future__ import annotations
import ast
import subprocess
from pathlib import Path

ROOT=Path("/opt/gaemigtp-news/app")
CHECKS={
 "backend/news_worker.py":("apply_worker_ai","apply_unchanged_worker_ai","save_snapshot","process_due_ai_snapshots"),
 "ops/staged_daily_groq_issues.py":("parse_issues","_keep_sourced_issues","analyze_news"),
 "ops/staged_ai_sequential_batch.py":("run_stock_batch","apply_worker_ai","apply_unchanged_worker_ai"),
 "ops/staged_auto_ai_daily.py":("reconcile_completed_ai_snapshots","process_due_ai_snapshots"),
 "ops/staged_ai_snapshot_integration.py":("with_ai_issue_briefs",),
 "backend/services/news_processed_store.py":("save_snapshot",),
}
for rel, names in CHECKS.items():
    p=ROOT/rel
    print("SOURCE",rel,"present",p.is_file(),flush=True)
    if not p.is_file():continue
    h=subprocess.run(["git","hash-object","--",str(p)],capture_output=True,text=True,check=True)
    print("SOURCE_BLOB_SHA",rel,h.stdout.strip(),flush=True)
    source=p.read_text(encoding="utf-8")
    try:t=ast.parse(source,filename=str(p))
    except SyntaxError as exc:
        print("SYNTAX_FAILED",rel,type(exc).__name__,flush=True)
        continue
    funcs={n.name:n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    for name in names:
        fn=funcs.get(name)
        print("FUNCTION",rel,name,bool(fn),flush=True)
        if fn and rel in ("ops/staged_daily_groq_issues.py","ops/staged_auto_ai_daily.py","ops/staged_ai_snapshot_integration.py"):
            print("FUNCTION_LINE",rel,name,fn.lineno,fn.end_lineno,flush=True)
    if rel=="backend/news_worker.py":
        for needle in ("apply_worker_ai(", "apply_unchanged_worker_ai(", "process_due_ai_snapshots(", "save_snapshot("):
            for n,line in enumerate(source.splitlines(),1):
                if needle in line:
                    print("WORKER_CALL",needle,n,line.strip()[:150],flush=True)
    if rel=="ops/staged_daily_groq_issues.py":
        for needle in ("Invalid article source IDs","_keep_sourced_issues(issues, news)","source_ids","max_completion_tokens"):
            count=sum(needle in line for line in source.splitlines())
            print("PARSER_TOKEN",needle,count,flush=True)
for prop in ("ActiveState","SubState","MainPID","ExecMainStartTimestamp"):
    output=subprocess.run(["systemctl","show","gaemigtp-news.service","-p",prop,"--value"],capture_output=True,text=True)
    print("SERVICE",prop,output.stdout.strip()[:100],flush=True)
print("READONLY_AI_AUDIT_COMPLETE",flush=True)
