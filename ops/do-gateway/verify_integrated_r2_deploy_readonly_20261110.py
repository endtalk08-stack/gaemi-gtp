"""Read-only integration R2 deploy verification, no API or secret values."""
from __future__ import annotations
import hashlib
import os
import subprocess
from pathlib import Path
root=Path("/opt/gaemigtp-news/app")
expected={
 "backend/news_worker.py":"1afca8927063b37052fb7186999e57c99dce53e9",
 "backend/services/r2_news_uploader.py":"a82a55129a263105e1a6dd41a45d3fa8f67ea781",
 "backend/services/news_processed_store.py":"33afbe04c9a4934791fb68f7c06c08739c33bfa3",
 "backend/services/news_r2_ai.py":"4079af35e4a8d97ee2231a1ce966fa72f795e9d8",
}
print("INTEGRATION_NEWS_R2_VERIFY_BEGIN")
all_ok=True
for rel,want in expected.items():
 p=root/rel
 if not p.is_file() or p.is_symlink():
  print("FILE_MISSING="+rel);all_ok=False;continue
 contents=p.read_bytes()
 sha=hashlib.sha1(b"blob "+str(len(contents)).encode()+b"\0"+contents).hexdigest()
 ok=sha==want
 print("INTEGRATION_FILE="+rel+" MATCH="+str(ok))
 all_ok&=ok
for unit in ("gaemigtp-news.service","gaemigtp-tradingview-news.service"):
 for prop in ("ActiveState","UnitFileState"):
  val=subprocess.run(["systemctl","show",unit,"--property="+prop,"--value"],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
  print("UNIT="+unit+" "+prop+"="+val)
  if unit=="gaemigtp-news.service" and val!=("inactive" if prop=="ActiveState" else "disabled"):
   all_ok=False
env=Path("/var/lib/gaemigtp-news/r2.env")
print("R2_ENV_EXISTS="+str(env.exists()))
try:
 if not env.is_symlink() and env.is_file() and os.access(env,os.R_OK):
  lines=env.read_text(encoding="utf-8").splitlines()
  modes=[s.split("=",1)[1].strip() for s in lines if s.startswith("GAEMIGTP_NEWS_STORAGE=")]
  print("R2_STORAGE_MODE="+",".join(modes))
  if modes!=["r2"]: all_ok=False
 else:
  print("R2_STORAGE_MODE=NOT_READABLE")
  all_ok=False
except OSError as exc:
 print("R2_MODE_READ_ERROR="+type(exc).__name__);all_ok=False
print("INTEGRATION_NEWS_R2_VERIFY_PASS="+str(all_ok))
raise SystemExit(0 if all_ok else 1)
