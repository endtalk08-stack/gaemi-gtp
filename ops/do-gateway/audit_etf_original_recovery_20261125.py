#!/usr/bin/env python3
from pathlib import Path
import subprocess, hashlib, re, os
root=Path("/opt/gaemigtp-news/app")
paths=["backend/kiwoom_us_top20_api.py","backend/kiwoom_us_live_prices.py","frontend/shell/left-market-sidebar/market-sidebar.js"]
for rel in paths:
 p=root/rel
 print("CURRENT",rel,"size",p.stat().st_size if p.exists() else "none")
 if p.exists(): print("CURRENT_META",rel,"mtime",int(p.stat().st_mtime),"sha256",hashlib.sha256(p.read_bytes()).hexdigest()[:20])
for rel in ("backend/kiwoom_us_top20_api.py","backend/kiwoom_us_live_prices.py"):
 p=root/rel
 if not p.exists(): continue
 lines=p.read_text(errors="replace").splitlines()
 keywords=("_etf_snapshot","_get_us_industry_etf_quotes","industry-quotes","_INDUSTRY_QUOTES","get_industry","ETF_FE_REFRESH","_set_industry_symbols","get_us_industry_symbols","_feed_snapshot")
 indices=[i for i,x in enumerate(lines) if any(k in x for k in keywords)]
 visited=set()
 print("SECTIONS",rel)
 for i in indices[:35]:
  for j in range(max(0,i-4),min(len(lines),i+8)):
   if j not in visited:
    print(str(j+1)+": "+lines[j][:210]);visited.add(j)
for base in (Path("/opt/gaemigtp-news"),Path("/var/backups")):
 if not base.exists():continue
 n=0
 for p in base.rglob("*"):
  if n>80:break
  if p.is_file() and not p.is_symlink() and ("kiwoom_us_top20_api" in p.name or "kiwoom_us_live_prices" in p.name) and p.suffix not in (".pyc",):
   try:
    st=p.stat()
    print("CANDIDATE",str(p)[:175],st.st_size,int(st.st_mtime),hashlib.sha256(p.read_bytes()).hexdigest()[:20])
    n+=1
   except (OSError,PermissionError):pass
try:
 r=subprocess.run(["git","-C",str(root),"log","-1","--format=%H %ci %s"],capture_output=True,text=True,timeout=6)
 print("LOCAL_GIT_HEAD",r.stdout.strip()[:240])
except Exception as ex: print("LOCAL_GIT_UNAVAILABLE",type(ex).__name__)
