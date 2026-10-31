"""Read-only TradingView news wiring audit. Never print credentials."""
from pathlib import Path
import os, subprocess
base=Path("/opt/gaemigtp-news/app")
for rel in ("backend/news_worker.py","backend/services/news_feed.py",
            "backend/providers/naver_news.py","backend/providers/tradingview_news.py"):
    present = (base/rel).is_file()
    print("SOURCE",rel,"PRESENT",present,flush=True)
    if present:
        r=subprocess.run(["git","hash-object","--",str(base/rel)],capture_output=True,text=True,timeout=10)
        print("SOURCE_SHA",rel,r.stdout.strip(),flush=True)
for keypath in ("/etc/gaemigtp/tradingview.env", "/etc/gaemigtp/news-worker.env"):
    try:
        st=Path(keypath).lstat()
        print("KEY_FILE",keypath,"PRESENT",True,"MODE",oct(st.st_mode & 0o777),flush=True)
    except PermissionError:
        print("KEY_FILE",keypath,"PROTECTED_DIRECTORY",True,flush=True)
    except FileNotFoundError:
        print("KEY_FILE",keypath,"MISSING",True,flush=True)
print("PROCESS_ENV_HAS_TRADINGVIEW_KEY",bool(os.environ.get("TRADINGVIEW_API_KEY")),flush=True)
for prop in ("ActiveState","UnitFileState","FragmentPath","DropInPaths","EnvironmentFiles","User","Group"):
    r=subprocess.run(["systemctl","show","gaemigtp-news.service","-p",prop],
        capture_output=True,text=True,timeout=10)
    print("SYSTEMD",r.stdout.strip()[:1200],flush=True)
r=subprocess.run(["systemctl","cat","gaemigtp-news.service"],capture_output=True,text=True,timeout=10)
for line in r.stdout.splitlines():
    l=line.strip()
    if l.startswith(("#","[", "User=", "Group=", "WorkingDirectory=", "EnvironmentFile=", "ExecStart=", "Restart=", "Description=")):
        print("UNIT_LINE",l[:350],flush=True)
print("AUDIT_COMPLETE",flush=True)
