#!/usr/bin/env python3
from pathlib import Path
import re, json, os

ROOT = Path("/opt/gaemigtp-news/app")
TERMS = re.compile(r"usa20550|usa20551|usa20540|usa20541|시가총액|market.?cap|market.?capital|trading.?value|키움|kiwoom", re.I)
SAFE = re.compile(r"usa20550|usa20551|usa20540|usa20541|시가총액|market.?cap|market.?capital|trading.?value|kiwoom|endpoint|api.?id|route|def |async def |class ", re.I)
SKIP = {".git","node_modules","venv",".venv","__pycache__",".next","dist","build"}
MAX_FILES = 1200
MAX_HITS = 160
files = []
hits = []
for p in ROOT.rglob("*"):
    if any(part in SKIP for part in p.parts) or not p.is_file():
        continue
    try:
        if p.stat().st_size > 1_000_000:
            continue
        rel = str(p.relative_to(ROOT))
        if p.suffix.lower() not in {".py",".js",".ts",".json",".yml",".yaml",".toml",".ini",".conf",".service"} and p.name not in {"Dockerfile"}:
            continue
        files.append(rel)
        text = p.read_text(errors="replace")
        for n,line in enumerate(text.splitlines(),1):
            if TERMS.search(line) and SAFE.search(line):
                low=line.lower()
                if any(x in low for x in ("api_key","secret","token","password","authorization","bearer")):
                    continue
                hits.append({"file":rel,"line":n,"text":line.strip()[:240]})
                if len(hits)>=MAX_HITS:
                    break
    except (OSError, UnicodeError):
        pass
    if len(files)>=MAX_FILES or len(hits)>=MAX_HITS:
        break
print(json.dumps({
  "root_exists": ROOT.exists(),
  "files_scanned": len(files),
  "relevant_hits": hits,
  "env_variable_names_only": sorted(k for k in os.environ if re.search(r"KIWOOM|APP|R2|QUOTE|MARKET",k,re.I))
}, ensure_ascii=False, indent=2))
