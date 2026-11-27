"""Read-only: confirm the deployed kiwoom_probe.py is the original blob."""
import hashlib
import pathlib
raw = pathlib.Path("/opt/gaemigtp-news/app/backend/kiwoom_probe.py").read_bytes()
blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
print("PROBE_BLOB=" + blob)
print("PROBE_RESTORED=" + str(blob == "aad06b9b3be06122ff29254f9632f7614e6f3ebe"))
