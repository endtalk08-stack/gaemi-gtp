"""Read-only classification of stale backups and Kiwoom probe files on DO.
Prints only path, stat ownership/mode and active process/module references;
no secrets, external calls or writes.
"""
from pathlib import Path
import os,stat,subprocess,sys
root=Path("/opt/gaemigtp-news/app")
files=[
"backend/kiwoom_us_live_prices.py",
"backend/kiwoom_us_price_relay.py",
"backend/kiwoom_us_value_collector.py",
"backend/kiwoom_fe_realtime_probe.py",
"backend/kiwoom_probe.py",
"backend/kiwoom_rank_probe.py",
"backend/news_worker.py.bak.1792189623",
"backend/news_worker.py.pre_coverage_20261018.bak",
"backend/news_worker.py.pre_groq_ai_20261017.bak",
"backend/services/news_feed.py.bak.1792190146",
"backend/services/news_feed.py.bak.1792191279",
"backend/services/news_feed.py.bak.before_restore.1792193590",
"backend/services/news_metadata_store.py.bak.1792191505",
"backend/services/news_metadata_store.py.bak.before_restore.1792193590",
"backend/services/news_processed_store.py.bak.1792189623",
"backend/services/us_market_close.py.bak-prompt-20261020",
"ops/.ai-primary-store-backup.sxZ3V0"
]
print("AUDIT_UID",os.getuid(), "EUID",os.geteuid(),flush=True)
for path in files:
 p=root/path
 if not p.exists():
  print("TARGET",path,"exists=no",flush=True);continue
 s=p.lstat()
 print("TARGET",path,"exists=yes","size="+str(s.st_size),
       "owner="+str(s.st_uid),"mode="+oct(stat.S_IMODE(s.st_mode)),
       "symlink="+str(p.is_symlink()).lower(),
       "parent_writable="+str(os.access(p.parent,os.W_OK)).lower(),flush=True)
try:
 p=subprocess.run(["systemctl","show","gaemigtp-kiwoom-us-fe.service","--property=ActiveState,ExecStart,MainPID"],capture_output=True,text=True,timeout=5)
 print("FE_SERVICE",p.stdout.replace("\n"," | ")[:850],flush=True)
 p=subprocess.run(["systemctl","show","gaemigtp-kiwoom-us-value.timer","--property=ActiveState,UnitFileState"],capture_output=True,text=True,timeout=5)
 print("VALUE_TIMER",p.stdout.replace("\n"," | ")[:380],flush=True)
except Exception as exc:
 print("SYSTEMD_READ_ERROR",type(exc).__name__,flush=True)
print("BACKUP_OWNER_AUDIT_COMPLETE",flush=True)
