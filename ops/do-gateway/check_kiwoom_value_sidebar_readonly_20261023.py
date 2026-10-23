"""Read-only production check: Render US value response and DO timer state.
No credentials, full JSON bodies or HTML content are logged.
"""
import subprocess
import requests

try:
    response = requests.get(
        "https://gaemi-gtp.onrender.com/market/trading-value",
        params={"market": "us"}, timeout=18, allow_redirects=False,
    )
    print("KIWOOM_VALUE_RENDER_HTTP=" + str(response.status_code), flush=True)
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    items = payload.get("items")
    print("KIWOOM_VALUE_RENDER_SOURCE=" + str(payload.get("source") or "unknown")[:35], flush=True)
    print("KIWOOM_VALUE_RENDER_ROWS=" + str(len(items) if isinstance(items,list) else -1), flush=True)
    if isinstance(items,list) and items:
        print("KIWOOM_VALUE_RENDER_FIRST_SYMBOL=" + str(items[0].get("symbol") or "")[:20], flush=True)
except Exception as exc:
    print("KIWOOM_VALUE_RENDER_ERROR_TYPE=" + type(exc).__name__, flush=True)

for action in ("is-enabled", "is-active"):
    try:
        x = subprocess.run(
            ["systemctl",action,"gaemigtp-kiwoom-us-value.timer"],
            capture_output=True,text=True,timeout=4,check=False,
        )
        state = x.stdout.strip().replace("\n"," ")[:32]
        print("KIWOOM_VALUE_TIMER_"+action.upper().replace("-","_")+"="+(state or "unknown"),flush=True)
    except Exception as exc:
        print("KIWOOM_VALUE_TIMER_"+action.upper().replace("-","_")+"_ERROR="+type(exc).__name__,flush=True)
