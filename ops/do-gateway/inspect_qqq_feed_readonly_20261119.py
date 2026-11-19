"""Read-only inspection of the active Kiwoom US live-price collector.
Prints unit/process metadata and bounded source excerpts only; never reads env values,
credentials, account data, orders, positions, databases, or market endpoints.
"""
import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path("/opt/gaemigtp-news/app")
TOKENS = ("kiwoom", "websocket", "price", "quote", "top20", "market")
NEEDLES = ("REG", "FE", "kiwoom_us", "websocket", "TOP20", "selected", "symbols")

def run(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=8)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return 99, type(exc).__name__

print("QQQ_READONLY_INSPECT_BEGIN", flush=True)
rc, units = run(["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--plain"])
for line in units.splitlines():
    low = line.lower()
    if "gaemigtp" in low and any(t in low for t in TOKENS):
        print("UNIT", line[:300], flush=True)

rc, processes = run(["ps", "-eo", "pid=,comm=,args="])
for line in processes.splitlines():
    low = line.lower()
    if "python" in low and any(t in low for t in ("kiwoom", "websocket", "price", "quote", "top20")):
        # Do not print arbitrary arguments or environment-like values.
        parts = line.strip().split(None, 2)
        if len(parts) >= 2:
            print("PROCESS", parts[0], parts[1], flush=True)

candidates = []
for base in (ROOT / "backend", ROOT / "ops"):
    if not base.exists() or base.is_symlink():
        continue
    for path in base.rglob("*.py"):
        if path.is_symlink() or not path.is_file():
            continue
        if any(t in path.name.lower() for t in TOKENS):
            candidates.append(path)
for path in sorted(set(candidates))[:100]:
    try:
        raw = path.read_bytes()
        if len(raw) > 300000:
            continue
        src = raw.decode("utf-8")
    except Exception:
        continue
    low = src.lower()
    if not any(n.lower() in low for n in NEEDLES):
        continue
    print("SOURCE", str(path.relative_to(ROOT)), "SHA256", hashlib.sha256(raw).hexdigest(), flush=True)
    lines = src.splitlines()
    hits = [i for i, line in enumerate(lines) if any(n.lower() in line.lower() for n in NEEDLES)]
    shown = set()
    for i in hits[:16]:
        for j in range(max(0, i-2), min(len(lines), i+3)):
            if j not in shown:
                # Exclude possible credentials or secret assignments.
                line = lines[j]
                if re.search(r"(secret|appkey|api.?key|token|password)", line, re.I) and "=" in line:
                    line = re.sub(r"(=).*", r"= [REDACTED]", line)
                print("  L" + str(j+1), line[:220], flush=True)
                shown.add(j)
print("QQQ_READONLY_INSPECT_END", flush=True)
