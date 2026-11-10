import json, re, subprocess, urllib.request
route = "/market/trading-value?market=us"
origin = "https://gaemigtp.com"
def check(label, url):
    try:
        req = urllib.request.Request(url, headers={"Origin": origin, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as res:
            data = json.loads(res.read(131072))
            print("TOP20_PROBE", label, res.status, data.get("source"), len(data.get("items") or []), data.get("captured_at"), "CORS", res.headers.get("Access-Control-Allow-Origin"), flush=True)
    except Exception as exc:
        print("TOP20_PROBE", label, type(exc).__name__, getattr(exc,"code",None), flush=True)
unit = "gaemigtp-kiwoom-us-top20-api.service"
pid = subprocess.check_output(["systemctl","show","-p","MainPID","--value",unit], text=True).strip()
listeners = subprocess.check_output(["ss","-ltnpH"], text=True)
ports = set()
for line in listeners.splitlines():
    if f"pid={pid}," in line:
        ports.add(line.split()[3].rsplit(":",1)[-1])
print("TOP20_LOCAL_PORTS", sorted(ports), flush=True)
for port in sorted(ports):
    if port.isdigit():
        check("local", "http://127.0.0.1:" + port + route)
check("external", "https://quotes.gaemigtp.com" + route)
