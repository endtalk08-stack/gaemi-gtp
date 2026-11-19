"""Read-only Kiwoom credential file access check. Never print secret values."""
import os
from pathlib import Path
p=Path("/etc/gaemigtp/kiwoom.env")
try:
    st=p.stat()
    print("KIWOOM_ENV_MODE="+oct(st.st_mode & 0o777),flush=True)
    print("KIWOOM_ENV_OWNER_UID="+str(st.st_uid),flush=True)
    print("KIWOOM_ENV_GROUP_GID="+str(st.st_gid),flush=True)
    print("KIWOOM_ENV_READABLE_BY_GATEWAY_USER="+str(os.access(p,os.R_OK)).lower(),flush=True)
    if os.access(p,os.R_OK):
        names=set()
        for line in p.read_text(encoding="utf-8").splitlines():
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            names.add(line.split("=",1)[0].strip().removeprefix("export ").strip())
        for name in sorted(names):
            if "KIWOOM" in name.upper() or "APP_KEY" in name.upper() or "APP_SECRET" in name.upper():
                print("KIWOOM_ENV_NAME="+name,flush=True)
except Exception as exc:
    print("KIWOOM_ENV_ACCESS_ERROR="+type(exc).__name__,flush=True)
