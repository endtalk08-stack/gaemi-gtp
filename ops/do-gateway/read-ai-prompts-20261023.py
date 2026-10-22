"""Read-only inspection of deployed AI prompt source; no providers or DB calls."""
import ast
import hashlib
from pathlib import Path

root = Path("/opt/gaemigtp-news/app")
files = (
    "ops/staged_daily_groq_issues.py",
    "ops/staged_ai_sequential_batch.py",
    "ops/staged_auto_ai_daily.py",
    "backend/services/us_market_close.py",
    "backend/news_worker.py",
)
safe_names = {"PROMPT", "US_CLOSE_PROMPT", "SYSTEM_PROMPT", "ISSUE_PROMPT", "AI_ISSUE_PROMPT"}

for relative in files:
    path = root / relative
    print("SOURCE_FILE", relative, "PRESENT", path.is_file(), flush=True)
    if not path.is_file():
        continue
    try:
        content = path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=relative)
    except (UnicodeError, OSError, SyntaxError) as exc:
        print("SOURCE_READ_ERROR", relative, type(exc).__name__, flush=True)
        continue
    data = content.encode("utf-8")
    print("SOURCE_SHA256", relative, hashlib.sha256(data).hexdigest(), flush=True)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names, value = [node.target.id], node.value
        else:
            continue
        for name in names:
            if name in safe_names and isinstance(value, ast.Constant) and isinstance(value.value, str):
                print("PROMPT_BEGIN", relative, name, "LINE", node.lineno, flush=True)
                print(value.value[:5500], flush=True)
                print("PROMPT_END", relative, name, flush=True)
    if relative in ("ops/staged_auto_ai_daily.py", "ops/staged_ai_sequential_batch.py"):
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.append(str(node.module or ""))
        print("AI_IMPORTS", relative, ",".join(sorted(set(imported))[:35]), flush=True)

print("READONLY_AI_PROMPT_INSPECTION_COMPLETE", flush=True)
