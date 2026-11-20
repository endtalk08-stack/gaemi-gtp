#!/usr/bin/env python3
from pathlib import Path
import re
ROOT=Path("/opt/gaemigtp-news/app")
targets=[
 "backend/providers/kiwoom_us_industry.py",
 "backend/providers/kiwoom_us_quotes.py",
 "backend/kiwoom_us_top20_api.py",
 "backend/kiwoom_rank_probe.py",
 "backend/services/kiwoom_us_value_board.py",
 "backend/services/market_rankings.py",
 "backend/providers/market_price.py",
]
for rel in targets:
 p=ROOT/rel
 if not p.is_file(): continue
 print("=== "+rel+" ===")
 for n,line in enumerate(p.read_text(errors="replace").splitlines(),1):
  if re.search(r"(APP_KEY|APP_SECRET|SECRET|TOKEN|PASSWORD|AUTHORIZATION)",line,re.I):
   line=re.sub(r"(['\"]).*?\1","'***'",line)
  print(f"{n}: {line[:350]}")
