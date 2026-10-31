"""Read-only TradingView stock-news connection audit; no credentials or network calls."""
from pathlib import Path
import os, subprocess, stat

base = Path("/opt/gaemigtp-news/app")
for rel in ("backend/news_worker.py", "backend/services/news_feed.py",
            "backend/providers/naver_news.py", "backend/providers/tradingview_news.py"):
    p = base / rel
    print("SOURCE", rel, "PRESENT", p.is_file(), flush=True)
for path in ("/etc/gaemigtp/tradingview.env", "/etc/gaemigtp/news-worker.env"):
    p = Path(path)
    try:
        st = p.lstat()
        print("KEY_FILE", path, "REGULAR", stat.S_ISREG(st.st_mode),
              "MODE", oct(stat.S_IMODE(st.st_mode)), "OWNER_UID", st.st_uid, flush=True)
    except FileNotFoundError:
        print("KEY_FILE", path, "MISSING", flush=True)
print("WORKER_ENV_HAS_TV_KEY", bool(os.environ.get("TRADINGVIEW_API_KEY")), flush=True)
for prop in ("ActiveState", "UnitFileState", "FragmentPath", "DropInPaths",
             "EnvironmentFiles", "User", "Group", "ExecStart"):
    r=subprocess.run(["systemctl","show","gaemigtp-news.service","-p",prop],
                     capture_output=True,text=True,timeout=10)
    v=r.stdout.strip()
    if prop=="ExecStart":
        v="PRESENT" if v and v!="ExecStart=" else "MISSING"
    if prop=="EnvironmentFiles":
        # Names only, no values.
        v=v[:1000]
    print("SYSTEMD", prop, v, flush=True)
print("AUDIT_COMPLETE",flush=True)
