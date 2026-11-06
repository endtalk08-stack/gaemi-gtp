from __future__ import annotations
import os
import subprocess
from pathlib import Path

base = Path("/var/lib/gaemigtp-news")
base.mkdir(parents=True, exist_ok=True)
key = base / "r2-bootstrap-key.pem"
pub = base / "r2-bootstrap-key.pub.pem"
if not key.exists():
    subprocess.run([
        "openssl","genpkey","-algorithm","RSA",
        "-pkeyopt","rsa_keygen_bits:3072","-out",str(key)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.chmod(key, 0o600)
if not pub.exists():
    subprocess.run([
        "openssl","pkey","-in",str(key),"-pubout","-out",str(pub)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.chmod(pub, 0o644)
print("GAEMI_R2_BOOTSTRAP_PUBLIC_KEY_BEGIN")
print(pub.read_text(encoding="utf-8").strip())
print("GAEMI_R2_BOOTSTRAP_PUBLIC_KEY_END")
