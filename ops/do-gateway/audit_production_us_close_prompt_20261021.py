"""Read-only exact production prompt audit. No writes, secrets or calls."""
import ast
import datetime
from pathlib import Path
p=Path("/opt/gaemigtp-news/app/backend/services/us_market_close.py")
print("PROD_PROMPT_AUDIT_PATH",str(p),flush=True)
if not p.is_file():
    print("PROD_PROMPT_AUDIT_MISSING",flush=True)
    raise SystemExit(2)
source=p.read_text(encoding="utf-8")
tree=ast.parse(source)
matches=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="US_CLOSE_PROMPT" for t in n.targets)]
print("PROD_PROMPT_AUDIT_MATCHES",len(matches),flush=True)
if len(matches)!=1:
    raise SystemExit(3)
value=ast.literal_eval(matches[0].value)
print("PROD_PROMPT_AUDIT_BEGIN",flush=True)
print(value,flush=True)
print("PROD_PROMPT_AUDIT_END",flush=True)
print("PROD_PROMPT_SOURCE_MTIME_UTC",datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat(),flush=True)
print("PROD_PROMPT_HAS_SOURCE_IDS","source_ids" in value,flush=True)
