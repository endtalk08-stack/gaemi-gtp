"""Read only TOP20 storage mode and systemd env layering; no credential disclosure."""
from __future__ import annotations
from pathlib import Path
import subprocess
import os

unit="gaemigtp-news.service"
print("TOP20_STORAGE_MODE_AUDIT_BEGIN")
p=subprocess.run(["systemctl","show",unit,"--property=ActiveState,UnitFileState,EnvironmentFiles","--no-pager"],capture_output=True,text=True,timeout=12,check=True)
for line in p.stdout.splitlines():
    if line.startswith("EnvironmentFiles="):
        value=line.split("=",1)[1]
        print("TOP20_UNIT_USES_R2_ENV="+str("r2.env" in value))
        print("TOP20_UNIT_USES_NEWS_ENV="+str("news-worker.env" in value))
        print("TOP20_UNIT_R2_ENV_AFTER_NEWS_ENV="+str(value.find("r2.env")>value.find("news-worker.env")>=0))
    else:
        print("TOP20_UNIT_"+line)
for label,path in (("NEWS",Path("/etc/gaemigtp/news-worker.env")),("R2",Path("/var/lib/gaemigtp-news/r2.env"))):
    print(label+"_ENV_EXISTS="+str(path.is_file() and not path.is_symlink()))
    if not path.is_file() or path.is_symlink() or not os.access(path,os.R_OK):
        continue
    modes=[]
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.lstrip().startswith("#") or "=" not in raw:continue
        k,v=raw.split("=",1)
        if k.strip()=="GAEMIGTP_NEWS_STORAGE":
            val=v.strip().strip("'\"").lower()
            modes.append(val if val in ("r2","neon","") else "other")
    print(label+"_STORAGE_MODE="+(",".join(modes) if modes else "unset"))
    print(label+"_ENV_WRITABLE="+str(os.access(path,os.W_OK)))
print("TOP20_STORAGE_MODE_AUDIT_END")
