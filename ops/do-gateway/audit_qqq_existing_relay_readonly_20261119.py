"""Read-only audit of the installed Kiwoom FE relay wiring. Never print secret values."""
import ast, hashlib, os, subprocess
from pathlib import Path

root=Path("/opt/gaemigtp-news/app")
relay=root/"backend/kiwoom_us_price_relay.py"
helper=root/"backend/kiwoom_us_live_prices.py"
unit=Path("/etc/systemd/system/gaemigtp-kiwoom-us-fe.service")

def run(label,args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=8)
        print("BEGIN_"+label+" EXIT="+str(p.returncode),flush=True)
        print((p.stdout or p.stderr or "").strip()[:5000],flush=True)
        print("END_"+label,flush=True)
    except Exception as e:
        print(label+"_ERROR="+type(e).__name__,flush=True)

for label,p in (("RELAY",relay),("HELPER",helper),("UNIT",unit)):
    print(label+"_EXISTS="+str(p.is_file()).lower(),flush=True)
    print(label+"_SYMLINK="+str(p.is_symlink()).lower(),flush=True)
    if p.is_file() and not p.is_symlink():
        raw=p.read_bytes()
        print(label+"_SHA256="+hashlib.sha256(raw).hexdigest(),flush=True)
        if label=="RELAY":
            try:
                tree=ast.parse(raw.decode("utf-8"))
                names=sorted(n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)))
                print("RELAY_TOP_LEVEL_NAMES="+",".join(names),flush=True)
                source=raw.decode("utf-8")
                for token in ("_ranked_symbols","_parse_price_event","REG","FE","us-price-push","Ed25519","QQQ"):
                    print("RELAY_HAS_"+token.replace("-","_").upper()+"="+str(token in source).lower(),flush=True)
                print("RELAY_LINES="+str(len(source.splitlines())),flush=True)
            except Exception as e:
                print("RELAY_PARSE_ERROR="+type(e).__name__,flush=True)
        elif label=="UNIT":
            print("UNIT_TEXT_BEGIN",flush=True)
            print(p.read_text(encoding="utf-8")[:7000],flush=True)
            print("UNIT_TEXT_END",flush=True)

run("UNIT_SHOW",["systemctl","show","gaemigtp-kiwoom-us-fe.service","--no-pager","-p","LoadState","-p","ActiveState","-p","SubState","-p","UnitFileState","-p","User","-p","Group","-p","ExecStart","-p","EnvironmentFiles","-p","Restart"])
run("UNIT_FILES",["systemctl","list-unit-files","--no-pager","gaemigtp-kiwoom-us-fe.service"])
run("PROCESS",["pgrep","-af","kiwoom_us_price_relay|gaemigtp-kiwoom-us-fe"])
for envfile in (Path("/etc/gaemigtp/kiwoom.env"),Path("/etc/gaemigtp/news-worker.env")):
    print("ENVFILE_"+envfile.name+"_READABLE="+str(os.access(envfile,os.R_OK)).lower(),flush=True)
    if envfile.is_file() and os.access(envfile,os.R_OK):
        names=[]
        for line in envfile.read_text(encoding="utf-8").splitlines():
            line=line.strip()
            if line and not line.startswith("#") and "=" in line:
                name=line.split("=",1)[0].strip().removeprefix("export ").strip()
                if "RELAY" in name.upper() or "PRICE" in name.upper() or "KIWOOM" in name.upper():
                    names.append(name)
        print("ENVFILE_"+envfile.name+"_RELEVANT_NAMES="+",".join(sorted(set(names))),flush=True)
print("QQQ_RELAY_AUDIT_COMPLETE",flush=True)
