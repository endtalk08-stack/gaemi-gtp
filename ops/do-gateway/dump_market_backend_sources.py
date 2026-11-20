#!/usr/bin/env python3
from pathlib import Path
ROOT=Path("/opt/gaemigtp-news/app")
targets=[
 "backend/providers/kiwoom_us_quotes.py",
 "backend/providers/kiwoom_us_rankings.py",
 "backend/providers/kiwoom_us_industry.py",
 "backend/kiwoom_us_top20_api.py",
 "backend/services/kiwoom_us_value_board.py",
 "backend/kiwoom_us_value_collector.py",
]
for rel in targets:
 p=ROOT/rel
 if not p.is_file(): continue
 print("=== "+rel+" ===")
 lines=p.read_text(errors="replace").splitlines()
 for n,line in enumerate(lines,1):
  print(f"{n}: {line[:400]}")
