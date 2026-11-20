#!/usr/bin/env python3
from pathlib import Path
import re
ROOT=Path("/opt/gaemigtp-news/app")
patterns=re.compile(r"kiwoom_us_quotes|issue_access_token|market/trading-value|trading_value|FastAPI|APIRouter|Flask|usa20540|usa20550|credentials_configured",re.I)
roots=[ROOT/"backend",ROOT/"app",ROOT/"."]
seen=set()
for base in roots:
 if not base.exists(): continue
 for p in base.rglob("*"):
  if not p.is_file() or p.suffix not in (".py",".js",".json"): continue
  if any(part in {".git","node_modules","__pycache__",".venv","venv"} for part in p.parts): continue
  try: lines=p.read_text(errors="replace").splitlines()
  except Exception: continue
  hits=[(i+1,line) for i,line in enumerate(lines) if patterns.search(line)]
  if not hits: continue
  rel=str(p.relative_to(ROOT))
  if rel in seen: continue
  seen.add(rel)
  print("=== "+rel+" ===")
  for n,line in hits[:100]:
   if re.search(r"(APP_KEY|APP_SECRET|SECRET|TOKEN|PASSWORD|AUTHORIZATION)",line,re.I):
    line=re.sub(r"(['\"]).*?\1","'***'",line)
   print(f"{n}: {line[:300]}")
