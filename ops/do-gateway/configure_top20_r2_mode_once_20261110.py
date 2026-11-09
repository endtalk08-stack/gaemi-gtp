"""Select TOP20 R2 storage mode in existing service-only R2 EnvironmentFile.

Credentials are preserved byte-for-byte. No services, DBs or news collection started.
"""
from __future__ import annotations
import os
import stat
import tempfile
import subprocess
from pathlib import Path

ENV=Path("/var/lib/gaemigtp-news/r2.env")
UNIT="gaemigtp-news.service"
def systemd(prop):
    p=subprocess.run(["systemctl","show",UNIT,"--property="+prop,"--value"],capture_output=True,text=True,timeout=12,check=True)
    return p.stdout.strip()

if systemd("ActiveState")!="inactive" or systemd("UnitFileState")!="disabled":
    raise SystemExit("TOP20_MODE_SETUP_ABORT_WORKER_NOT_STOPPED")
raw_envfiles=systemd("EnvironmentFiles")
if "/var/lib/gaemigtp-news/r2.env" not in raw_envfiles:
    raise SystemExit("TOP20_MODE_SETUP_ABORT_R2_ENV_NOT_LINKED")
if ENV.is_symlink() or not ENV.is_file():
    raise SystemExit("TOP20_MODE_SETUP_ABORT_UNSAFE_ENV")
st=ENV.stat()
if (st.st_mode & 0o777)!=0o600:
    raise SystemExit("TOP20_MODE_SETUP_ABORT_ENV_PERMISSIONS")
if not os.access(ENV,os.W_OK):
    raise SystemExit("TOP20_MODE_SETUP_ABORT_ENV_NOT_WRITABLE")
before=ENV.read_bytes()
if len(before)>8192 or b"\0" in before:
    raise SystemExit("TOP20_MODE_SETUP_ABORT_INVALID_ENV")
lines=before.decode("utf-8").splitlines()
keys=set()
for raw in lines:
    if raw.startswith("#") or not raw.strip():
        continue
    if "=" not in raw:
        raise SystemExit("TOP20_MODE_SETUP_ABORT_INVALID_LINE")
    key=raw.split("=",1)[0].strip()
    if key in keys:
        raise SystemExit("TOP20_MODE_SETUP_ABORT_DUPLICATE_ENV_KEY")
    keys.add(key)
if not {"R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY"}.issubset(keys):
    raise SystemExit("TOP20_MODE_SETUP_ABORT_CREDENTIALS_MISSING")
existing=[line.split("=",1)[1].strip() for line in lines if line.startswith("GAEMIGTP_NEWS_STORAGE=")]
if existing:
    if existing != ["r2"]:
        raise SystemExit("TOP20_MODE_SETUP_ABORT_MODE_CONFLICT")
    print("TOP20_R2_MODE_ALREADY_SET=True")
else:
    after=before + (b"" if before.endswith(b"\n") else b"\n") + b"GAEMIGTP_NEWS_STORAGE=r2\n"
    fd,name=tempfile.mkstemp(prefix=".top20-r2-mode-",dir=str(ENV.parent))
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as handle:
            handle.write(after)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name,ENV)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    print("TOP20_R2_MODE_SET=True")
check=ENV.read_bytes()
if not check.startswith(before) and not existing:
    raise SystemExit("TOP20_MODE_SETUP_CREDENTIAL_PRESERVATION_FAILED")
if (ENV.stat().st_mode & 0o777)!=0o600:
    raise SystemExit("TOP20_MODE_SETUP_PERMISSIONS_CHANGED")
print("TOP20_R2_CREDENTIALS_PRESERVED=True")
print("TOP20_R2_NEWS_SERVICE_ACTIVE="+systemd("ActiveState"))
print("TOP20_R2_NEWS_SERVICE_ENABLED="+systemd("UnitFileState"))
print("TOP20_R2_MODE_CONFIG_SUCCESS")
