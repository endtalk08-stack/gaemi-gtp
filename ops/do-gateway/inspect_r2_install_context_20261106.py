from __future__ import annotations
import os, pwd
from pathlib import Path

print("RUN_USER=" + pwd.getpwuid(os.geteuid()).pw_name)
for raw in ("/var/lib/gaemigtp-news", "/opt/gaemigtp-news/app", "/home/gaemi-deploy/.gaemi-gateway"):
    p=Path(raw)
    print(
        "PATH=%s exists=%s writable=%s readable=%s" %
        (raw, p.exists(), os.access(p, os.W_OK), os.access(p, os.R_OK))
    )
key=Path("/var/lib/gaemigtp-news/r2-bootstrap-key.pem")
print("PRIVATE_KEY readable=%s exists=%s" % (os.access(key, os.R_OK), key.exists()))
