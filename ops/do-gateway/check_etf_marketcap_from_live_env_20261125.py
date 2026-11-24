import os,sys
from pathlib import Path
sys.path.insert(0,"/opt/gaemigtp-news/app")
# Reuse the environment of the already-running quote service without printing secrets.
needles=("kiwoom_us_top20_api.py","backend.kiwoom_us_top20_api")
found=[]
for entry in os.scandir("/proc"):
 if not entry.name.isdigit(): continue
 try:
  raw=Path("/proc",entry.name,"cmdline").read_bytes()
  if any(n in raw.decode("utf-8","ignore") for n in needles):
   found.append(entry.name)
 except (OSError,PermissionError): pass
print("API_PIDS",found[:5],flush=True)
if not found: raise SystemExit("API_PROCESS_NOT_FOUND")
pid=found[0]
try:
 envraw=Path("/proc",pid,"environ").read_bytes().split(b"\0")
 loaded=0
 for item in envraw:
  if b"=" not in item: continue
  k,v=item.split(b"=",1)
  key=k.decode("utf-8","ignore")
  if key.startswith(("KIWOOM_","APP_KEY","APP_SECRET")):
   os.environ[key]=v.decode("utf-8","ignore");loaded+=1
 print("SERVICE_ENV_KEYS_LOADED",loaded,flush=True)
except (OSError,PermissionError) as exc:
 raise SystemExit("SERVICE_ENV_READ_"+type(exc).__name__)
from backend.providers.kiwoom_us_industries import ETF_TICKERS,fetch_us_etf_marketcap
try:
 snap=fetch_us_etf_marketcap(limit=100)
 rows=snap.get("items",[]) if isinstance(snap,dict) else []
 found={r.get("symbol"):r.get("exchange") for r in rows if isinstance(r,dict) and r.get("symbol") in ETF_TICKERS}
 print("MARKETCAP_OK",snap.get("ok"),"ROWS",len(rows),"ETF_FOUND",len(found),"ETF_MAP",sorted(found.items()),flush=True)
 print("ETF_MISSING",sorted(ETF_TICKERS-set(found)),flush=True)
except Exception as exc:
 print("MARKETCAP_ERROR",type(exc).__name__,str(exc)[:180],flush=True)
