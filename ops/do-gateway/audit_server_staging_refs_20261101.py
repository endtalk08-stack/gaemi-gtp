"""Read-only inventory of staged/temporary app files and live references."""
from pathlib import Path
import os, time, json, re

APP=Path("/opt/gaemigtp-news/app")
OPS=APP/"ops"
roots=[APP/"backend", APP/"frontend", APP/"app.py", OPS/"systemd", Path("/etc/systemd/system"), Path("/etc/cron.d"), Path("/etc/cron.daily"), Path("/etc/cron.hourly")]
candidates=[]
for p in OPS.iterdir():
    if p.is_file() and (p.name.startswith("staged_") or p.name.endswith(".next") or (p.name.startswith(".") and p.suffix in (".py",".sh"))):
        if "backup" in p.name.lower() or p.name==".groq_api_key":
            continue
        st=p.stat()
        candidates.append({"path":str(p),"name":p.name,"bytes":st.st_size,"age_days":round((time.time()-st.st_mtime)/86400,1)})
print("CANDIDATE_COUNT",len(candidates),flush=True)
for c in candidates:
    name=c["name"]
    refs=[]
    for root in roots:
        if not root.exists(): continue
        files=[root] if root.is_file() else root.rglob("*")
        for f in files:
            try:
                if not f.is_file() or f.is_symlink() or f==Path(c["path"]): continue
                if f.stat().st_size>2_000_000: continue
                raw=f.read_bytes()
                if name.encode() in raw:
                    refs.append(str(f))
            except (OSError,PermissionError):
                pass
    # ops helper scripts may reference other staged files; list exact matches
    print("CANDIDATE",json.dumps(c,ensure_ascii=False),flush=True)
    print("REFERENCED_BY",json.dumps(sorted(set(refs)),ensure_ascii=False),flush=True)
print("READ_ONLY_STAGING_REFERENCE_AUDIT_DONE",flush=True)
