"""Read-only pre-deploy comparison for the existing TOP20 HTTPS process."""
import hashlib, subprocess
from pathlib import Path
root=Path("/opt/gaemigtp-news/app")
paths=[
 root/"backend/kiwoom_us_top20_api.py",
 Path("/etc/systemd/system/gaemigtp-kiwoom-us-top20-https.service"),
]
for p in paths:
    print("FILE",str(p),"EXISTS",p.is_file(),"SYMLINK",p.is_symlink(),flush=True)
    if p.is_file() and not p.is_symlink():
        raw=p.read_bytes()
        print("SHA256",p.name,hashlib.sha256(raw).hexdigest(),"BYTES",len(raw),flush=True)
        if p.suffix==".service":
            print("UNIT_TEXT_BEGIN",flush=True)
            print(raw.decode("utf-8")[:7000],flush=True)
            print("UNIT_TEXT_END",flush=True)
try:
    r=subprocess.run(["systemctl","show","gaemigtp-kiwoom-us-top20-https.service",
        "--no-pager","-p","LoadState","-p","ActiveState","-p","SubState",
        "-p","User","-p","Group","-p","ExecStart","-p","EnvironmentFiles"],
        capture_output=True,text=True,timeout=8)
    print("UNIT_RUNTIME_BEGIN",flush=True);print(r.stdout.strip(),flush=True);print("UNIT_RUNTIME_END",flush=True)
except Exception as exc:
    print("UNIT_RUNTIME_ERROR",type(exc).__name__,flush=True)
print("TOP20_HTTPS_PREDEPLOY_AUDIT_COMPLETE",flush=True)
