from pathlib import Path
import hashlib
root=Path("/opt/gaemigtp-news/app")
paths=["backend/providers/kiwoom_us_industries.py","backend/kiwoom_us_live_prices.py","backend/kiwoom_us_top20_api.py"]
for rel in paths:
 p=root/rel
 print("FILE",rel,"size",p.stat().st_size,"sha256",hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
 s=p.read_text(errors="replace").splitlines()
 if rel.endswith("kiwoom_us_industries.py"):
  starts=[i for i,x in enumerate(s) if x.startswith("def fetch_us_etf_exchanges(") or x.startswith("def fetch_us_etf_quotes(")]
 elif rel.endswith("kiwoom_us_live_prices.py"):
  starts=[i for i,x in enumerate(s) if "def run_qqq_fe_stream" in x or "def _register_fe" in x]
 else:
  starts=[i for i,x in enumerate(s) if x.startswith("def get_us_etf_symbols(") or x.startswith("def _get_us_industry_etf_quotes(")]
 for i in starts:
  end=next((j for j in range(i+1,len(s)) if s[j].startswith("def ") or s[j].startswith("async def ")),min(len(s),i+100))
  print("SECTION",rel,i+1,"\n"+"\n".join(f"{j+1}: {s[j]}" for j in range(i,min(end,i+120))),flush=True)
