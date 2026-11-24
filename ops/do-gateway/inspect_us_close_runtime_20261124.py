#!/usr/bin/env python3
"""Read-only source/permissions fingerprint for US market-close deployment."""
from pathlib import Path
import hashlib, json, os, subprocess, urllib.request
root = Path("/opt/gaemigtp-news/app")
for rel in ("backend/us_quote_change.py","backend/kiwoom_us_top20_api.py",
            "backend/kiwoom_us_live_prices.py","backend/providers/kiwoom_us_industries.py"):
    p = root / rel
    if not p.is_file() or p.is_symlink():
        print("SOURCE",rel,"MISSING"); continue
    data = p.read_bytes()
    gitsha = hashlib.sha1(("blob "+str(len(data))+"\\0").encode()+data).hexdigest()
    print("SOURCE", rel, "GIT_SHA", gitsha, "SIZE", len(data))
for p in (Path("/var/lib/gaemigtp-news"), root / "backend"):
    print("LOCATION",str(p),"exists",p.is_dir(),"write_as_gateway_user",os.access(p,os.W_OK))
for name in ("gaemigtp-kiwoom-us-top20-api.service",
             "gaemigtp-kiwoom-us-top20-https.service"):
    check = subprocess.run(["systemctl","show",name,"-p","ActiveState","-p","User","-p","Group"],
                           text=True,capture_output=True,timeout=5)
    print("UNIT",name,"status",check.returncode,check.stdout.strip().replace("\\n",","))
for endpoint in ("http://127.0.0.1:8765/health",):
    try:
        with urllib.request.urlopen(endpoint, timeout=3) as f:
            val = json.load(f)
        print("API",endpoint,"ok",val.get("ok"),"service",val.get("service"))
    except Exception as e:
        print("API",endpoint,"result",type(e).__name__)
print("INSPECT_CLOSE_RUNTIME_OK")
