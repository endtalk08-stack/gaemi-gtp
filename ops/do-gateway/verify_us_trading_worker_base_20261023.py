"""Read-only verification of running US news worker before a single scoped TOP20 edit."""
import ast
import subprocess
from pathlib import Path

root = Path("/opt/gaemigtp-news/app")
for name in ("backend/news_worker.py", "ops/staged_daily_groq_issues.py"):
    src = root / name
    if not src.is_file() or src.is_symlink():
        raise SystemExit("MISSING_SOURCE " + name)
    tree = ast.parse(src.read_text(encoding="utf-8"), filename=name)
    blob = subprocess.check_output(["git", "hash-object", str(src)], text=True).strip()
    print("RUNNING_BLOB", name, blob, flush=True)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [x.id for x in node.targets if isinstance(x, ast.Name)]
            if "RANKING_ENDPOINTS" in targets:
                print("RUNNING_RANKING_ENDPOINTS", ast.literal_eval(node.value), flush=True)
            if "PROMPT" in targets:
                value = ast.literal_eval(node.value)
                print("RUNNING_PROMPT_BEGIN", flush=True)
                print(value, flush=True)
                print("RUNNING_PROMPT_END", flush=True)
print("WORKER_BASE_READONLY_VERIFIED", flush=True)
