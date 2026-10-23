"""Read-only references check for Kiwoom legacy Neon live-price writer.
Print only filenames and token-match line numbers; no source values/secrets.
"""
import os,re,subprocess
from pathlib import Path
base=Path("/opt/gaemigtp-news/app")
keys=("_persist(","_one_connection(","kiwoom_us_live_prices","kiwoom_us_price_relay","read_us_live_quotes")
for key in keys:
 matches=[]
 for scope in ("backend","ops","scripts","tests"):
  d=base/scope
  if not d.is_dir():continue
  for f in d.rglob("*"):
   if not f.is_file() or f.is_symlink() or f.suffix not in (".py",".sh",".service",".timer",".yml",".yaml") or f.stat().st_size>200000:continue
   try:
    text=f.read_text("utf-8")
   except Exception:continue
   for i,line in enumerate(text.splitlines(),1):
    if key in line:
     matches.append(str(f.relative_to(base))+":"+str(i))
 print("REFERENCE",key,"count",len(matches),"locations",repr(matches[:45]),flush=True)
try:
 d=Path("/etc/systemd/system")
 for f in sorted(d.glob("gaemigtp-*.service")):
  if not f.is_file():continue
  text=f.read_text("utf-8")
  print("LIVE_UNIT",f.name,"uses_legacy="+str("backend.kiwoom_us_live_prices" in text),"uses_relay="+str("backend.kiwoom_us_price_relay" in text),flush=True)
except Exception as e:
 print("SYSTEMD_READ_ERROR",type(e).__name__,flush=True)
print("BACKUP_GATEWAY_DIR_EXISTS",Path("/var/backups/gaemi-gateway").is_dir(),flush=True)
print("KIWOOM_REFERENCES_COMPLETE",flush=True)
