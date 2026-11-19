"""Read-only review of the installed project gateway's public command dispatch."""
from pathlib import Path
p=Path("/usr/local/sbin/gaemi-do-gateway")
try:
    st=p.stat()
    print("GATEWAY_FILE_MODE="+oct(st.st_mode & 0o777),flush=True)
    print("GATEWAY_FILE_OWNER_UID="+str(st.st_uid),flush=True)
    source=p.read_text(encoding="utf-8")
    print("GATEWAY_SOURCE_BEGIN",flush=True)
    print(source[:24000],flush=True)
    print("GATEWAY_SOURCE_END",flush=True)
except Exception as exc:
    print("GATEWAY_SOURCE_ERROR="+type(exc).__name__,flush=True)
