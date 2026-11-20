#!/usr/bin/env python3
from pathlib import Path
import re, json
ROOT=Path("/opt/gaemigtp-news/app")
TARGETS=[
 "backend/providers/kiwoom_us_rankings.py",
 "backend/providers/kiwoom_us_quotes.py",
 "backend/kiwoom_us_value_collector.py",
 "backend/market_api.py",
 "backend/kiwoom_probe.py",
]
SECRET=re.compile(r"(API[_-]?KEY|SECRET|TOKEN|PASSWORD|CLIENT[_-]?SECRET|AUTHORIZATION)",re.I)
for rel in TARGETS:
 p=ROOT/rel
 if not p.is_file():
  continue
 out=[]
 for n,line in enumerate(p.read_text(errors="replace").splitlines(),1):
  if SECRET.search(line):
   line=re.sub(r"(['\"]).*?\1","'***'",line)
  out.append(f"{n}: {line}")
 print("=== "+rel+" ===")
 print("\n".join(out[:260]))
