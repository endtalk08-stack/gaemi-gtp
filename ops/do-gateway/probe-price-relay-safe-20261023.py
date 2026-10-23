"""Read-only prerequisites for DO -> Render signed price relay."""
import importlib.util
import os
import pathlib
import shutil
import subprocess
for name in ("requests", "websockets", "cryptography", "psycopg"):
    print("RELAY_MODULE_" + name.upper() + "=" + str(bool(importlib.util.find_spec(name))).lower(), flush=True)
print("RELAY_OPENSSL_BIN=" + str(bool(shutil.which("openssl"))).lower(), flush=True)
try:
    p=subprocess.run(["openssl","version"],capture_output=True,text=True,timeout=4)
    print("RELAY_OPENSSL_VERSION=" + (p.stdout.strip()[:100] if p.returncode==0 else "unavailable"), flush=True)
except Exception as e:
    print("RELAY_OPENSSL_ERROR="+type(e).__name__,flush=True)
print("RELAY_UID="+str(os.getuid()),flush=True)
home=pathlib.Path.home()
print("RELAY_HOME="+str(home),flush=True)
print("RELAY_HOME_EXISTS="+str(home.is_dir()).lower(),flush=True)
print("RELAY_HOME_WRITABLE="+str(os.access(home,os.W_OK)).lower(),flush=True)
for unit in ("gaemigtp-kiwoom-us-fe.service","gaemigtp-news.service"):
    p=subprocess.run(["systemctl","is-active",unit],capture_output=True,text=True,timeout=5)
    print("RELAY_UNIT_"+unit+"="+p.stdout.strip(),flush=True)
print("RELAY_PROBE_COMPLETE",flush=True)
