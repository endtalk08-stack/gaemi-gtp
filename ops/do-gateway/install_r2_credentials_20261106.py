from __future__ import annotations

import os
from pathlib import Path

SOURCE = Path("/home/gaemi-deploy/.gaemi-gateway/r2.env")
TARGET_DIR = Path("/etc/gaemigtp")
TARGET = TARGET_DIR / "r2.env"
ALLOWED = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")

if os.geteuid() != 0:
    raise SystemExit("R2_INSTALL_REQUIRES_ROOT")
if not SOURCE.is_file() or SOURCE.is_symlink():
    raise SystemExit("R2_INSTALL_SOURCE_MISSING")

values = {}
for raw in SOURCE.read_text(encoding="utf-8").splitlines():
    if not raw or "=" not in raw:
        continue
    key, value = raw.split("=", 1)
    if key not in ALLOWED or not value or "\n" in value or "\r" in value:
        raise SystemExit("R2_INSTALL_SOURCE_INVALID")
    values[key] = value
if tuple(values.keys()) != ALLOWED:
    raise SystemExit("R2_INSTALL_KEYS_MISSING")

TARGET_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
os.chmod(TARGET_DIR, 0o700)
tmp = TARGET_DIR / ".r2.env.tmp"
with tmp.open("w", encoding="utf-8") as f:
    for key in ALLOWED:
        f.write(f"{key}={values[key]}\n")
os.chmod(tmp, 0o600)
os.chown(tmp, 0, 0)
os.replace(tmp, TARGET)
SOURCE.unlink(missing_ok=True)

st = TARGET.stat()
if st.st_uid != 0 or st.st_gid != 0 or (st.st_mode & 0o777) != 0o600:
    raise SystemExit("R2_INSTALL_PERMISSIONS_FAILED")
print("R2_CREDENTIALS_INSTALLED")
print("R2_CREDENTIAL_VALUES_NOT_LOGGED")
