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
