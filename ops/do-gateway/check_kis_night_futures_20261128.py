"""Read-only: is the KIS night-futures feed deployed and does the quote service see credentials?"""
import hashlib, pathlib, subprocess
for rel in ("backend/kis_night_futures_feed.py", "backend/kiwoom_us_top20_api.py"):
    p = pathlib.Path("/opt/gaemigtp-news/app", rel)
    if p.exists():
        raw = p.read_bytes()
        print("BLOB %s %s" % (rel, hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()), flush=True)
    else:
        print("BLOB %s missing" % rel, flush=True)
try:
    import cryptography
    print("CRYPTOGRAPHY", cryptography.__version__, flush=True)
except Exception as exc:
    print("CRYPTOGRAPHY_MISSING", type(exc).__name__, flush=True)
out = subprocess.run(["journalctl", "--no-pager", "-u", "gaemigtp-kiwoom-us-top20-https.service", "-n", "400"],
                     text=True, capture_output=True).stdout
for line in out.splitlines():
    if "KIS" in line or "night" in line.lower():
        print("LOG " + line[-200:], flush=True)
print("LOG_LINES_SCANNED", len(out.splitlines()), flush=True)
