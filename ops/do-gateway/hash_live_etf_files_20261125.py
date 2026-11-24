import subprocess,hashlib
from pathlib import Path
root=Path("/opt/gaemigtp-news/app")
for rel in ("backend/kiwoom_us_top20_api.py","backend/kiwoom_us_live_prices.py","backend/providers/kiwoom_us_industries.py"):
 p=root/rel
 data=p.read_bytes()
 blob=subprocess.check_output(["git","hash-object",str(p)],text=True).strip()
 print("SERVER_FILE",rel,"bytes",len(data),"git_blob",blob,"sha256",hashlib.sha256(data).hexdigest(),flush=True)
