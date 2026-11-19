"""Read-only inspection of the existing DigitalOcean gateway permissions and unit definitions."""
import subprocess

def run(label, argv, limit=6000):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=8)
        out=(p.stdout or "")+(p.stderr or "")
        print("BEGIN",label,"EXIT",p.returncode,flush=True)
        print(out[:limit],flush=True)
        print("END",label,flush=True)
    except Exception as exc:
        print("ERROR",label,type(exc).__name__,flush=True)

run("SUDO_ALLOWLIST",["sudo","-n","-l"],4000)
for unit in (
 "gaemigtp-kiwoom-us-top20-api.service",
 "gaemigtp-kiwoom-us-top20-https.service",
 "gaemigtp-tradingview-news.service",
 "gaemigtp-kiwoom-us-value.timer",
):
    run("UNIT_"+unit,["systemctl","cat",unit],5000)
run("GATEWAY_OWNER",["id"],1000)
