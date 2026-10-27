"""Read-only preflight: verify deployed selector EXACTLY matches the approved GitHub source before changing step 4."""
import hashlib
from pathlib import Path
p=Path("/opt/gaemigtp-news/app/backend/services/news_signal_enrichment.py")
assert p.is_file() and not p.is_symlink(),"LIVE_SOURCE_MISSING_OR_SYMLINK"
data=p.read_bytes()
actual=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
expected="a737a4de2c9abfefca9c751e1a2a8fe92a4a3cd5"
s=data.decode("utf-8")
print("LIVE_SELECTOR_GIT_BLOB_SHA="+actual,flush=True)
print("EXPECTED_SELECTOR_GIT_BLOB_SHA="+expected,flush=True)
print("PRIOR_EVENT_MERGE_PRESENT="+str(s.count("for old in previous or []:")==1),flush=True)
if actual!=expected:raise SystemExit("STOP_LIVE_CODE_GIT_MISMATCH")
if s.count("for old in previous or []:")!=1:raise SystemExit("STOP_PRIOR_MERGE_SCOPE_MISMATCH")
print("PRIOR_EVENT_MERGE_PREFLIGHT_OK",flush=True)
