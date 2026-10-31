#!/usr/bin/env python3
"""Remove only verified disposable TradingView test output and owned Python bytecode."""
import json, os, stat, time
from pathlib import Path

uid=os.getuid()
removed=[]
skipped=[]
test=Path("/run/gaemi-gateway/nvda-news-test-20261028.json")
try:
    st=test.lstat()
    if not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):
        skipped.append({"path":str(test),"reason":"not_regular_file"})
    elif st.st_uid != uid:
        skipped.append({"path":str(test),"reason":"not_owned_by_job_user"})
    elif time.time()-st.st_mtime < 48*3600:
        skipped.append({"path":str(test),"reason":"not_old_enough"})
    else:
        with test.open("r",encoding="utf-8") as f:
            payload=json.load(f)
        if not isinstance(payload,(dict,list)):
            skipped.append({"path":str(test),"reason":"unexpected_json_shape"})
        else:
            size=st.st_size
            test.unlink()
            removed.append({"path":str(test),"bytes":size,"kind":"old_one_time_NVDA_test_output"})
except FileNotFoundError:
    skipped.append({"path":str(test),"reason":"already_absent"})
except Exception as e:
    skipped.append({"path":str(test),"reason":type(e).__name__})

app=Path("/opt/gaemigtp-news/app")
pyc_count=0
pyc_bytes=0
for root, dirs, files in os.walk(app,topdown=True,followlinks=False):
    dirs[:]=[d for d in dirs if d!=".git" and not (Path(root)/d).is_symlink()]
    if Path(root).name != "__pycache__":
        continue
    for name in files:
        if not name.endswith(".pyc"):
            continue
        p=Path(root)/name
        try:
            st=p.lstat()
            if stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode) and st.st_uid==uid:
                size=st.st_size
                p.unlink()
                pyc_count+=1
                pyc_bytes+=size
        except Exception:
            continue
    try:
        Path(root).rmdir()
    except OSError:
        pass
if pyc_count:
    removed.append({"path":str(app)+"/**/__pycache__/*.pyc","files":pyc_count,"bytes":pyc_bytes,"kind":"regenerable_python_bytecode"})
print(json.dumps({"result":"completed","removed":removed,"skipped":skipped,"scope":"only old owned test JSON and owned app pyc files","service_state_changed":False,"system_logs_or_backups_touched":False},ensure_ascii=False))
