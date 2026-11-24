#!/usr/bin/env python3
from pathlib import Path
import hashlib, subprocess
root=Path("/opt/gaemigtp-news/app")
paths=("backend/us_quote_change.py","backend/kiwoom_us_top20_api.py","backend/kiwoom_us_live_prices.py","backend/providers/kiwoom_us_industries.py")
for rel in paths:
 p=root/rel
 data=p.read_bytes()
 correct=hashlib.sha1(("blob "+str(len(data))+"\0").encode()+data).hexdigest()
 cmd=subprocess.run(["git","hash-object","--",str(p)],capture_output=True,text=True,timeout=5)
 print("FILE",rel,"size",len(data),"sha",correct,"git",cmd.stdout.strip(),"mtime",round(p.stat().st_mtime),flush=True)
for cmd in (["git","-C",str(root),"rev-parse","--is-inside-work-tree"],["git","-C",str(root),"status","--short","--"]+list(paths)):
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=5)
 print("GIT",r.returncode,r.stdout[:500].replace("\n"," | "),r.stderr[:100].replace("\n"," | "),flush=True)
