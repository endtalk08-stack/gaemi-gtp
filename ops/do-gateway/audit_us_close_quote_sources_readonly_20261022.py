"""Read-only audit of US market-close quote path installed on DigitalOcean.
No API calls, credentials, DB, AI requests, imports of app modules, or mutations.
"""
from pathlib import Path
import hashlib
import re
import subprocess

APP=Path("/opt/gaemigtp-news/app")
files=[
 ("us_close", "backend/services/us_market_close.py"),
 ("us_runtime", "backend/services/us_market_close_runtime.py"),
 ("kiwoom", "backend/providers/kiwoom_us_quotes.py"),
 ("market_price", "backend/providers/market_price.py"),
 ("news_worker", "backend/news_worker.py"),
]
signals={
 "naver_index_api":r"stock\.naver\.com/api/polling/worldstock/index",
 "naver_aggregate":r"stock\.naver\.com/api/stockSecurity",
 "yahoo":r"query[12]\.finance\.yahoo\.com|yfinance",
 "kiwoom_api":r"api\.kiwoom\.com",
 "kiwoom_module":r"kiwoom_us_quotes|fetch_us_close|fetch_us_quote",
 "verified_indices":r"verified_indices\(",
 "verified_originals":r"verified_originals\(",
 "run_once":r"def run_once\(",
 "news_calls":r"fetch_news\(",
}
for label,rel in files:
    p=APP/rel
    if not p.is_file():
        print("AUDIT_FILE "+label+"=missing",flush=True); continue
    b=p.read_bytes()
    txt=b.decode("utf-8","replace")
    sha=hashlib.sha256(b).hexdigest()[:16]
    print("AUDIT_FILE "+label+"=present bytes="+str(len(b))+" sha256_16="+sha,flush=True)
    for signal,pattern in signals.items():
        match=[str(i) for i,line in enumerate(txt.splitlines(),1) if re.search(pattern,line,re.I)]
        if match:
            print("AUDIT_SIGNAL "+label+"."+signal+"=" + ",".join(match[:15]),flush=True)
    if label=="us_runtime":
        for line in txt.splitlines():
            if "INDEX_CODES =" in line:
                print("AUDIT_INDEX_CODES="+line.strip()[:190],flush=True)
for unit in ("gaemigtp-news.service","gaemigtp-us-market-close.timer","gaemigtp-us-market-close.service"):
    r=subprocess.run(["systemctl","is-active",unit],capture_output=True,text=True,timeout=7)
    print("AUDIT_UNIT "+unit+"="+r.stdout.strip(),flush=True)
r=subprocess.run(["systemctl","show","gaemigtp-us-market-close.service","-p","ExecStart","-p","UnitFileState","--no-pager"],capture_output=True,text=True,timeout=7)
for line in r.stdout.splitlines():
    if line.startswith("ExecStart="):
        normalized=" ".join(line.split())
        # Print only executable path and module evidence; no arguments/env.
        print("AUDIT_US_CLOSE_SERVICE_EXECUTABLE_MENTION="+
              str("backend.us_market_close" in normalized or "us_market_close" in normalized).lower(),flush=True)
    elif line.startswith("UnitFileState="):
        print("AUDIT_US_CLOSE_SERVICE_"+line,flush=True)
print("AUDIT_READONLY_DONE",flush=True)
