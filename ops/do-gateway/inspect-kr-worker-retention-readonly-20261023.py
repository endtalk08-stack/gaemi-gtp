"""Exact read-only audit of domestic-news control-flow, retention, and leftovers.
No network/API/DB writes, no file edits, and no credential values printed.
"""
from pathlib import Path
import ast, re, subprocess, os, time
ROOT=Path("/opt/gaemigtp-news/app")
def show_file(rel,ranges):
 p=ROOT/rel
 print("SECTION",rel,"exists",p.is_file(),flush=True)
 if not p.is_file():return
 lines=p.read_text("utf-8").splitlines()
 for a,b in ranges:
  print("LINES",a,b,flush=True)
  for n in range(a-1,min(b,len(lines))):
   s=lines[n]
   if any(k in s.lower() for k in ("secret","password","api_key","app_key","client_id","token","database_url","authorization","credential","os.environ","getenv(")):
    s="[redacted configuration or key related]"
   print(str(n+1).rjust(3),s[:225],flush=True)
show_file("backend/news_worker.py",[(15,104),(129,180)])
p=ROOT/"backend/services/news_processed_store.py"
if p.is_file():
 lines=p.read_text("utf-8").splitlines()
 tree=ast.parse("\n".join(lines))
 wanted={"purge_expired_original_news","purge_expired","read_snapshot","save_snapshot","mark_checked"}
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in wanted:
   print("STORE_FUNCTION",node.name,"start",node.lineno,"end",node.end_lineno,flush=True)
   a,b=node.lineno,min(node.end_lineno,node.lineno+65)
   for n in range(a-1,b):
    s=lines[n]
    if any(k in s.lower() for k in ("secret","password","api_key","token","database_url","authorization","credential","getenv(")):
     s="[redacted configuration or key related]"
    print("STORE_LINE",n+1,s[:210],flush=True)
# Only project-specific service / timer / cron paths, not their sensitive content.
for d in (Path("/etc/systemd/system"),Path("/etc/cron.d"),Path("/etc/cron.daily"),Path("/etc/cron.hourly")):
 try:
  names=sorted(x.name for x in d.iterdir() if ("gaemi" in x.name.lower() or "news" in x.name.lower() or "kiwoom" in x.name.lower()))
  print("UNIT_CRON_NAMES",str(d),repr(names[:80]),flush=True)
 except Exception as exc:
  print("UNIT_CRON_ERROR",str(d),type(exc).__name__,flush=True)
try:
 p=subprocess.run(["crontab","-l"],capture_output=True,text=True,timeout=4)
 print("CRONTAB_LIST_STATUS",p.returncode,"gaemigtp_entries",sum("gaemi" in x.lower() for x in p.stdout.splitlines()),flush=True)
except Exception as exc:print("CRONTAB_LIST_ERROR",type(exc).__name__,flush=True)
# Exact candidates from deployed source directories only; no /var/backups purging.
patterns=("*.bak*","*.old","*.orig","*.tmp","*.swp")
for folder in ("backend","ops"):
 p=ROOT/folder
 if not p.is_dir():continue
 for pattern in patterns:
  files=sorted(x for x in p.rglob(pattern) if x.is_file())
  print("BACKUP_COUNT",folder,pattern,len(files),flush=True)
  for f in files[:35]:
   print("BACKUP_FILE",str(f.relative_to(ROOT)),f.stat().st_size,int(time.time()-f.stat().st_mtime),flush=True)
print("EXACT_KR_AUDIT_COMPLETE",flush=True)
