"""Read-only audit of live DigitalOcean price direction wiring; no network or DB calls."""
import ast
import hashlib
from pathlib import Path
import subprocess

root = Path("/opt/gaemigtp-news/app")
sources = {
    "worker": "backend/news_worker.py",
    "ai_batch": "ops/staged_ai_sequential_batch.py",
    "ai_model": "ops/staged_daily_groq_issues.py",
}
loaded = {}
for role, rel in sources.items():
    p = root / rel
    print("FILE", role, rel, "PRESENT", p.is_file(), flush=True)
    if not p.is_file() or p.is_symlink():
        continue
    raw = p.read_bytes()
    try:
        source = raw.decode("utf-8")
        tree = ast.parse(source)
    except (UnicodeError, SyntaxError) as exc:
        print("SOURCE_PARSE_ERROR", role, type(exc).__name__, flush=True)
        continue
    print("SHA256", role, hashlib.sha256(raw).hexdigest(), flush=True)
    loaded[role] = (source, tree)

def calls_with_kw(tree, func_name, kw):
    return any(isinstance(n, ast.Call)
               and ((isinstance(n.func, ast.Name) and n.func.id == func_name)
                    or (isinstance(n.func, ast.Attribute) and n.func.attr == func_name))
               and any(x.arg == kw for x in n.keywords)
               for n in ast.walk(tree))

def functions(tree):
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

if "worker" in loaded:
    s, t = loaded["worker"]
    fs = functions(t)
    print("WORKER_RANKING_FETCH_FN", "read_ranked_stocks" in fs, flush=True)
    print("WORKER_RANKING_QUOTE_CAPTURE", "_RANKED_PRICES" in s and "change_pct" in s, flush=True)
    print("WORKER_CURRENT_PRICE_FIELD", 'row.get("price")' in s or "row.get('price')" in s, flush=True)
    print("WORKER_CHANGE_PCT_FIELD", 'row.get("change_pct")' in s or "row.get('change_pct')" in s, flush=True)
    print("WORKER_PASSES_PRICE_CONTEXT_ON_NEW", calls_with_kw(t, "apply_worker_ai", "price_context"), flush=True)
    print("WORKER_PASSES_PRICE_CONTEXT_ON_UNCHANGED", calls_with_kw(t, "apply_unchanged_worker_ai", "price_context"), flush=True)
    print("WORKER_HAS_RANKED_PRICE_CACHE", "_RANKED_PRICES" in s, flush=True)
    print("WORKER_RANKING_ENDPOINTS", "RANKING_ENDPOINTS" in s, flush=True)
if "ai_batch" in loaded:
    s, t = loaded["ai_batch"]
    print("AI_BATCH_HAS_PRICE_CONTEXT_PARAM", any(n.name == "apply_worker_ai" and any(a.arg == "price_context" for a in n.args.kwonlyargs+n.args.args) for n in ast.walk(t) if isinstance(n, ast.FunctionDef)), flush=True)
    print("AI_BATCH_PASSES_CONTEXT_TO_MODEL", calls_with_kw(t, "analyze_news", "price_context") or 'price_context=stock.get("price_context")' in s, flush=True)
if "ai_model" in loaded:
    s, t = loaded["ai_model"]
    print("AI_MODEL_ACCEPTS_PRICE_CONTEXT", any(n.name == "analyze_news" and any(a.arg == "price_context" for a in n.args.kwonlyargs+n.args.args) for n in ast.walk(t) if isinstance(n, ast.FunctionDef)), flush=True)
    print("AI_MODEL_REQUIRES_NUMERIC_CHANGE", 'change_pct' in s and 'change == 0' in s, flush=True)
try:
    result=subprocess.run(["systemctl","is-active","gaemigtp-news.service"],capture_output=True,text=True,timeout=3)
    print("NEWS_WORKER_ACTIVE", result.stdout.strip()=="active", flush=True)
except (OSError, subprocess.TimeoutExpired) as exc:
    print("SERVICE_STATUS_ERROR",type(exc).__name__,flush=True)
print("READONLY_PRICE_CONTEXT_AUDIT_COMPLETE",flush=True)
