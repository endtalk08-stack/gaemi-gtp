"""Read-only inspect of local Kiwoom TOP20 exchange for three missing chart symbols."""
import sys
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.kiwoom_us_top20_api import read_top20
data=read_top20()
print("LOCAL_TOP20_CAPTURED="+str(data.get("captured_at")),flush=True)
for sym in ("GEV","TSM","FOXA"):
    items=[x for x in data["items"] if x["symbol"]==sym]
    if items:
        r=items[0]
        print("LOCAL_TOP20_SYMBOL="+sym+" EXCHANGE="+str(r["exchange"])+" RANK="+str(r["rank"]),flush=True)
    else:
        print("LOCAL_TOP20_SYMBOL="+sym+" ABSENT",flush=True)
