"""Read-only KR news collection / Neon persistence / debris audit on existing DO worker.

No API calls, database changes, worker restarts, or file deletions.
Secrets and environment values are never printed (except selected safe configuration).
"""
from pathlib import Path
import ast
import hashlib
import os
import re
import subprocess
import datetime

APP=Path("/opt/gaemigtp-news/app")
print("AUDIT_UTC",datetime.datetime.now(datetime.timezone.utc).isoformat(),flush=True)
print("AUDIT_APP_EXISTS",APP.is_dir(),flush=True)
print("AUDIT_UID",os.getuid(),flush=True)
allowed_env=("NEWS_WORKER_INTERVAL_SECONDS","NEWS_WORKER_RANKING_URL","NEWS_WORKER_STOCKS","NEWS_WORKER_KR_STOCKS","NEWS_WORKER_US_STOCKS","NEWS_WORKER_MARKET","NEWS_WORKER_US_ONLY","NEWS_WORKER_KR_ENABLED","NEWS_WORKER_NEWS_SOURCE","NEWS_WORKER_DART_ENABLED")
for key in allowed_env:
    val=os.getenv(key,"")
    if key=="NEWS_WORKER_RANKING_URL":
        print("CONFIG",key,"configured="+str(bool(val)),flush=True)
    elif "STOCKS" in key:
        vals=[x.strip()[:80] for x in val.split(",") if x.strip()]
        print("CONFIG",key,"count="+str(len(vals)),"values="+repr(vals[:90]),flush=True)
    else:
        print("CONFIG",key,"value="+(val[:95] if val else "<unset>"),flush=True)
for key in ("NEWS_DATABASE_URL","DATABASE_URL","NAVER_CLIENT_ID","NAVER_CLIENT_SECRET","ALPACA_API_KEY","OPENDART_API_KEY"):
    print("CONFIG_PRESENT",key,bool(os.getenv(key)),flush=True)

def safe(cmd, timeout=7):
    try:
        r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout)
        return (r.returncode,r.stdout.strip()[:15000],r.stderr.strip()[:220])
    except Exception as e:
        return (999,"",type(e).__name__)

for name in ("gaemigtp-news.service","gaemigtp-kiwoom-us-fe.service","gaemigtp-kiwoom-us-value.timer","gaemigtp-disclosures.service","gaemigtp-disclosures.timer"):
    c,out,err=safe(["systemctl","show",name,"--property=Id,ActiveState,SubState,UnitFileState,ExecMainPID,FragmentPath,NextElapseUSecRealtime,ExecStart"],5)
    print("UNIT",name,"rc",c,"show",out[:750].replace("\n"," || "),flush=True)
rc,out,err=safe(["systemctl","list-units","--all","--plain","--no-legend","gaemigtp-*"],6)
print("UNITS_LIST_BEGIN",flush=True)
for line in out.splitlines()[:55]:
    print("UNIT_ROW",line[:210],flush=True)
print("UNITS_LIST_END",flush=True)
rc,out,err=safe(["systemctl","list-timers","--all","--no-pager","--plain"],7)
for line in out.splitlines():
    if "gaemigtp" in line.lower() or "kiwoom" in line.lower():
        print("TIMER",line[:200],flush=True)

for name in ("backend/news_worker.py","backend/services/news_processed_store.py","backend/services/news_processed_results_store.py","backend/services/news_feed.py","backend/services/engine.py","ops/staged_ai_sequential_batch.py"):
    p=APP/name
    print("FILE",name,"exists",p.is_file(),"symlink",p.is_symlink(),flush=True)
    if not p.is_file() or p.is_symlink():continue
    try:
        txt=p.read_text("utf-8")
        t=ast.parse(txt)
        funcs=[n.name for n in t.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
        imports=[n.module for n in ast.walk(t) if isinstance(n,ast.ImportFrom) and n.module]
        print("FILE_META",name,"lines",len(txt.splitlines()),"sha256",hashlib.sha256(txt.encode()).hexdigest()[:16],"functions",repr(funcs[:55]),flush=True)
        if name=="backend/news_worker.py":
            print("NEWS_WORKER_IMPORTS",repr(imports[:45]),flush=True)
            lines=txt.splitlines()
            focus=("NEWS_WORKER_STOCKS","NEWS_WORKER_INTERVAL","read_ranked_stocks","market","MARKET","stock_name","news_processed","save_","persist_","fetch_stock_news","_should_","US_ONLY","KR_ONLY","ranked","apply_worker_ai","while True","sleep(","gaemigtp")
            hits=[i for i,line in enumerate(lines) if any(q in line for q in focus)]
            masks=("KEY","TOKEN","SECRET","PASS","AUTH","DATABASE_URL","os.environ","getenv","password")
            print("WORKER_MATCHED_LINE_COUNT",len(hits),flush=True)
            for i in hits[:135]:
                ln=lines[i]
                if any(k.lower() in ln.lower() for k in masks):ln="[configuration line redacted]"
                print("WORKER_LINE",i+1,ln.strip()[:190],flush=True)
    except Exception as e:
        print("SOURCE_READ_ERROR",name,type(e).__name__,flush=True)

rc,out,err=safe(["ps","-eo","pid,ppid,etimes,user,args","--no-headers"],8)
for line in out.splitlines():
    lo=line.lower()
    if "gaemigtp" in lo and any(k in lo for k in ("python","gunicorn","node","cron")):
        if any(k in lo for k in ("secret","token","password","-key","api_key")):
            line="<redacted command>"
        print("PROCESS",line[:230],flush=True)

print("GARBAGE_CANDIDATES_BEGIN",flush=True)
for sub in ("backend","ops","scripts"):
    p=APP/sub
    if not p.is_dir():continue
    count=0
    for f in sorted(p.rglob("*")):
        if count>110:break
        if f.is_symlink():
            print("SYMLINK",str(f.relative_to(APP))[:200],flush=True);count+=1
        elif f.is_file():
            path=str(f.relative_to(APP))
            low=path.lower()
            if any(k in low for k in (".bak",".old",".orig",".tmp","staged_","backup","debug","probe","test_", "oneoff", "one_shot", "scratch","__pycache__")):
                if not f.name.endswith(".pyc"):
                    print("CANDIDATE",path[:175],"size",f.stat().st_size,flush=True);count+=1
print("GARBAGE_CANDIDATES_END",flush=True)
print("READ_ONLY_KR_NEWS_AUDIT_COMPLETE",flush=True)
