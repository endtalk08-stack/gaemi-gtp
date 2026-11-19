"""Read-only inspection of the active Kiwoom US live-price collector.
No environment values, credentials, orders, positions, databases, or market requests.
"""
import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path("/opt/gaemigtp-news/app")
TOKENS = ("kiwoom", "websocket", "price", "quote", "top20", "market", "relay")

def run(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=8)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 99, type(exc).__name__

print("QQQ_READONLY_INSPECT_BEGIN", flush=True)
_, units = run(["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--plain"])
for line in units.splitlines():
    if "gaemigtp" in line.lower():
        print("UNIT", line[:300], flush=True)

_, processes = run(["ps", "-eo", "pid=,comm="])
for line in processes.splitlines():
    parts=line.strip().split(None,1)
    if len(parts)!=2: continue
    pid,comm=parts
    if comm.lower() not in ("python","python3","gunicorn","uvicorn"):
        continue
    try:
        cgroup=Path("/proc",pid,"cgroup").read_text()[:500].replace("\n",";")
        exe=Path("/proc",pid,"exe").resolve()
        print("PYPROC",pid,"COMM",comm,"EXE",str(exe),"CGROUP",cgroup,flush=True)
    except Exception:
        pass

for base in (ROOT / "backend", ROOT / "ops"):
    if not base.exists() or base.is_symlink(): continue
    for path in sorted(base.rglob("*.py")):
        if path.is_symlink() or not path.is_file(): continue
        if not any(t in path.name.lower() for t in TOKENS): continue
        try:
            raw=path.read_bytes()
            if len(raw)>300000: continue
            src=raw.decode("utf-8")
        except Exception: continue
        print("SOURCE",str(path.relative_to(ROOT)),"SHA256",hashlib.sha256(raw).hexdigest(),flush=True)
        for i,line in enumerate(src.splitlines(),1):
            if any(t in line.lower() for t in ("websocket","trnm","reg","fe","top20","symbol","relay")):
                if re.search(r"(secret|appkey|api.?key|token|password)",line,re.I) and "=" in line:
                    line=re.sub(r"(=).*",r"= [REDACTED]",line)
                print("  L"+str(i),line[:220],flush=True)
                if i>350: break
print("QQQ_READONLY_INSPECT_END",flush=True)
