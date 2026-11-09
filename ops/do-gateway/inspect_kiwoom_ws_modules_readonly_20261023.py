"""One-shot read-only check of runtime websocket dependencies and public TLS route.
No credentials, trading/account APIs, subscriptions or orders used.
"""
import importlib.util
import socket
import ssl
import sys

for module in ("websockets", "websocket", "aiohttp"):
    try:
        present = importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        present = False
    print("KIWOOM_WS_MODULE_" + module.upper() + "=" + str(present).lower(), flush=True)

host, port = "api.kiwoom.com", 10000
try:
    with socket.create_connection((host, port), timeout=6) as plain:
        plain.settimeout(6)
        context = ssl.create_default_context()
        with context.wrap_socket(plain, server_hostname=host) as tls:
            print("KIWOOM_WS_TLS_OK=" + str(tls.version()), flush=True)
except (OSError, ssl.SSLError, TimeoutError) as exc:
    print("KIWOOM_WS_TLS_FAIL_TYPE=" + type(exc).__name__, flush=True)
    sys.exit(2)

# Read-only inventory of existing HTTP/WebSocket ingress paths on DigitalOcean.
import os
import pathlib
import subprocess
for unit in ("nginx.service", "caddy.service", "cloudflared.service",
             "gaemigtp-kiwoom-us-value.timer", "gaemigtp-news.service"):
    try:
        p=subprocess.run(["systemctl","show",unit,"--property=ActiveState,UnitFileState",
                          "--no-pager"],capture_output=True,text=True,timeout=4)
        print("INGRESS_UNIT="+unit+" "+p.stdout.strip().replace("\\n"," "),flush=True)
    except Exception as exc: print("INGRESS_UNIT_ERROR="+unit+" "+type(exc).__name__)
try:
    p=subprocess.run(["ss","-ltn"],capture_output=True,text=True,timeout=6)
    for line in p.stdout.splitlines():
        if line.startswith("State"):continue
        parts=line.split()
        if len(parts)>=4:print("INGRESS_LISTEN="+parts[3],flush=True)
except Exception as exc:print("INGRESS_LISTEN_ERROR="+type(exc).__name__)
for directory in ("/etc/nginx/sites-enabled","/etc/caddy","/etc/cloudflared"):
    p=pathlib.Path(directory)
    if p.is_dir():
        print("INGRESS_DIR="+directory+" FILES="+",".join(x.name for x in p.iterdir() if x.is_file()),flush=True)
