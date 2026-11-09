"""Inspect existing news-worker unit's R2 credential wiring without secrets or changes."""
from __future__ import annotations
from pathlib import Path
import subprocess
import os
print("NEWS_R2_UNIT_AUDIT_BEGIN=1")
for unit in ("gaemigtp-news.service","gaemigtp-tradingview-news.service","gaemigtp-kiwoom-us-value.service"):
    p=subprocess.run(["systemctl","show",unit,"--property=LoadState,ActiveState,UnitFileState,EnvironmentFiles,ExecStart","--no-pager"],capture_output=True,text=True,timeout=10)
    fields={}
    for line in p.stdout.splitlines():
        key,_,value=line.partition("=")
        if key=="ExecStart":
            # Executable path only; command arguments/env must not be logged.
            fields[key]="set" if value else "not_set"
        elif key=="EnvironmentFiles":
            # Only expected path presence, not secret values.
            fields["primary_env"]="news-worker.env" in value
            fields["r2_env"]="r2.env" in value
        else:
            fields[key]=value
    print("UNIT="+unit+" STATUS="+str(fields))
for name,path in (("NEWS_ENV",Path("/etc/gaemigtp/news-worker.env")),("R2_ENV",Path("/var/lib/gaemigtp-news/r2.env"))):
    print(name+"_EXISTS="+str(path.is_file()))
    print(name+"_READABLE="+str(os.access(path,os.R_OK)))
    if path.is_file() and not path.is_symlink() and os.access(path,os.R_OK):
        names=set()
        for line in path.read_text(encoding="utf-8").splitlines():
            line=line.strip()
            if line.startswith("export "):
                line=line[7:].strip()
            if not line or line.startswith("#") or "=" not in line: continue
            names.add(line.split("=",1)[0].strip())
        for key in ("GAEMIGTP_NEWS_STORAGE","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","GAEMIGTP_NEWS_AI_PAUSED","GAEMIGTP_NEWS_AI_R2_ENABLED"):
            print(name+"_HAS_"+key+"="+str(key in names))
print("NEWS_R2_UNIT_AUDIT_END=1")
