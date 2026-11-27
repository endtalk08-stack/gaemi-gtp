"""Read-only: print the deployed kiwoom_probe.py (diagnostic module, no secrets) as base64."""
import base64
import hashlib
import pathlib

path = pathlib.Path("/opt/gaemigtp-news/app/backend/kiwoom_probe.py")
raw = path.read_bytes()
print("PROBE_BLOB=" + hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(), flush=True)
encoded = base64.b64encode(raw).decode()
for i in range(0, len(encoded), 200):
    print("B64:" + encoded[i:i + 200], flush=True)
