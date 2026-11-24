#!/usr/bin/env python3
from pathlib import Path
import datetime as dt
roots=[Path("/var/lib/gaemigtp-news"),Path("/opt/gaemigtp-news/app")]
keys=("quote","close","kiwoom","top20","industry","sector","etf")
for root in roots:
 if not root.is_dir(): continue
 for p in root.rglob("*"):
  if not p.is_file() or p.is_symlink() or not any(k in p.name.lower() for k in keys): continue
  if any(k in str(p).lower() for k in ("env","secret","token","credential","key","pem","cert")): continue
  st=p.stat()
  if root.name=="app" and "/backend/" in str(p): continue
  if st.st_size>2000000: continue
  print("CANDIDATE",p.relative_to(root),st.st_size,dt.datetime.fromtimestamp(st.st_mtime,dt.timezone.utc).isoformat(),flush=True)
