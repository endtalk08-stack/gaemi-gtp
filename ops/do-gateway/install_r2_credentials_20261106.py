from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path("/opt/gaemigtp-news/app/backend/r2-bootstrap.enc")
PRIVATE_KEY = Path("/var/lib/gaemigtp-news/r2-bootstrap-key.pem")
TARGET_DIR = Path("/var/lib/gaemigtp-news")
TARGET = TARGET_DIR / "r2.env"
ALLOWED = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")

if not SOURCE.is_file() or SOURCE.is_symlink():
    raise SystemExit("R2_INSTALL_SOURCE_MISSING")
if not PRIVATE_KEY.is_file() or PRIVATE_KEY.is_symlink():
    raise SystemExit("R2_INSTALL_PRIVATE_KEY_MISSING")
if not TARGET_DIR.is_dir() or TARGET_DIR.is_symlink():
    raise SystemExit("R2_INSTALL_TARGET_DIR_UNSAFE")
if not os.access(TARGET_DIR, os.W_OK):
    raise SystemExit("R2_INSTALL_TARGET_NOT_WRITABLE")

plain_path = None
try:
    fd, plain_name = tempfile.mkstemp(prefix=".r2-plain-", dir=str(TARGET_DIR))
    os.close(fd)
    plain_path = Path(plain_name)
    os.chmod(plain_path, 0o600)
    subprocess.run(
        [
            "openssl", "pkeyutl", "-decrypt",
            "-inkey", str(PRIVATE_KEY),
            "-in", str(SOURCE),
            "-out", str(plain_path),
            "-pkeyopt", "rsa_padding_mode:oaep",
            "-pkeyopt", "rsa_oaep_md:sha256",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    values = {}
    for raw in plain_path.read_text(encoding="utf-8").splitlines():
        if not raw or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        if key not in ALLOWED or not value or "\n" in value or "\r" in value:
            raise SystemExit("R2_INSTALL_SOURCE_INVALID")
        values[key] = value
    if set(values) != set(ALLOWED):
        raise SystemExit("R2_INSTALL_KEYS_MISSING")

    tmp = TARGET_DIR / ".r2.env.tmp"
    with tmp.open("w", encoding="utf-8") as out:
        for key in ALLOWED:
            out.write(f"{key}={values[key]}\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, TARGET)
finally:
    if plain_path is not None:
        plain_path.unlink(missing_ok=True)

if (TARGET.stat().st_mode & 0o777) != 0o600:
    raise SystemExit("R2_INSTALL_PERMISSIONS_FAILED")
print("R2_CREDENTIALS_INSTALLED")
print("R2_CREDENTIAL_VALUES_NOT_LOGGED")
