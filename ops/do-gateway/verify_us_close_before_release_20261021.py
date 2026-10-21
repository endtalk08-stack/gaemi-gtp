"""Read-only DigitalOcean verification before deploying US-close model 2."""
from pathlib import Path
import ast, hashlib, json
from subprocess import run
p=Path("/opt/gaemigtp-news/app/backend/services/us_market_close.py")
if not p.is_file():
    raise SystemExit("US_CLOSE_EXISTING_MISSING")
b=p.read_bytes()
tree=ast.parse(b.decode("utf-8"))
names={}
for n in tree.body:
    if isinstance(n,ast.Assign):
        for target in n.targets:
            if isinstance(target,ast.Name) and target.id in ("US_CLOSE_PROMPT","MODEL"):
                try: names[target.id]=ast.literal_eval(n.value)
                except ValueError: pass
print("US_CLOSE_EXISTING_BLOB="+hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest())
print("US_CLOSE_EXISTING_MODEL="+str(names.get("MODEL")))
print("US_CLOSE_EXISTING_PROMPT="+repr(names.get("US_CLOSE_PROMPT")))
for service in ("gaemigtp-news.service","gaemigtp-us-market-close.timer"):
    r=run(["systemctl","is-active",service],capture_output=True,text=True,timeout=5)
    print(service+"="+r.stdout.strip())
print("US_CLOSE_READ_ONLY_VERIFIED")
