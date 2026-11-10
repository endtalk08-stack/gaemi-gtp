import json, re, subprocess, urllib.request
route = "/market/trading-value?market=us"
origin = "https://gaemi-gtp.onrender.com"
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

for label, extra in [("origin_tls", ["--resolve","quotes.gaemigtp.com:443:127.0.0.1","-k"]), ("cloudflare", [])]:
    result = subprocess.run(["curl","--noproxy","*","-sS","--max-time","8","-i","-H","Origin: "+origin,*extra,"https://quotes.gaemigtp.com"+route],capture_output=True,text=True)
    head, _, body = result.stdout.partition("\n\n")
    headers = [line for line in head.splitlines() if line.lower().startswith(("http/","server:","cf-ray:","cf-mitigated:","content-type:","access-control-allow-origin:"))]
    print("EDGE_PROBE",label,result.returncode,headers,flush=True)
    try:
        parsed = json.loads(body)
        print("EDGE_BODY",label,len(parsed.get("items") or []),parsed.get("error"),flush=True)
    except ValueError:
        print("EDGE_BODY",label,re.findall(r"<title>([^<]+)|error code:? (\\d+)|Error (\\d{4})",body,re.I)[:5],flush=True)
