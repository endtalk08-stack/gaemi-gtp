"""Read only metadata R2 credentials presence and execution environment configuration.

Never print secret values or invoke Kiwoom, Neon, or Cloudflare endpoints.
"""
import os
import re
import subprocess
from pathlib import Path

for name in ("gaemigtp-kiwoom-us-daily.service","gaemigtp-news.service"):
    for prop in ("EnvironmentFiles","FragmentPath","DropInPaths"):
        r=subprocess.run(("systemctl","show",name,"--property="+prop,"--value"),capture_output=True,text=True,timeout=5)
        print("UNIT",name,prop,(r.stdout.strip() or "none")[:200],flush=True)

for path in ("/var/lib/gaemigtp-news/r2.env", "/etc/gaemigtp/news-worker.env"):
    p=Path(path)
    try:
        lines=p.read_text(encoding="utf-8").splitlines()
        names=[]
        for line in lines:
            m=re.match(r"^(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=",line.strip())
            if m: names.append(m.group(1))
        print("ENV_READ",p.name,"yes",flush=True)
        for key in ("NEWS_DATABASE_URL","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","GAEMIGTP_NEWS_STORAGE"):
            print("KEY_PRESENT",p.name,key,key in names,flush=True)
    except OSError as e:
        print("ENV_READ",p.name,type(e).__name__,flush=True)
