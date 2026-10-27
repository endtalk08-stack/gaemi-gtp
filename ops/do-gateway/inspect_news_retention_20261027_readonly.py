"""Read-only operational inspection for 24-hour news retention, no DB calls or writes."""
import ast
import hashlib
from pathlib import Path

root = Path("/opt/gaemigtp-news/app")
targets = {
    "backend/services/news_processed_store.py": {
        "purge_expired", "save_snapshot", "_prefer_same_day_ai", "_fresh_ai_briefs"
    },
    "backend/news_worker.py": {"run_once", "main"},
}
for rel, names in targets.items():
    p = root / rel
    assert p.is_file() and not p.is_symlink(), "missing_or_symlink:" + rel
    data = p.read_bytes()
    print("LIVE_FILE", rel, "sha256", hashlib.sha256(data).hexdigest(), "bytes", len(data), flush=True)
    source = data.decode("utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            print("FUNCTION", rel, node.name, node.lineno, node.end_lineno, flush=True)
            for index in range(node.lineno - 1, node.end_lineno):
                line = lines[index]
                if any(word in line.upper() for word in ("PASSWORD", "PRIVATE_KEY", "SECRET", "ACCESS_TOKEN")):
                    line = "[redacted]"
                print(str(index + 1) + ":" + line[:240], flush=True)
print("RETENTION_READ_ONLY_INSPECTION_COMPLETE", flush=True)
