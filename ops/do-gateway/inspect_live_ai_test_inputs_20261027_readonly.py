"""Read-only inspect deployed AI issue and US-close model configurations."""
import ast
import hashlib
from pathlib import Path
root = Path("/opt/gaemigtp-news/app")
targets = {
    "ops/staged_daily_groq_issues.py": {"MODEL", "PROMPT"},
    "backend/services/us_market_close.py": {"MODEL", "US_CLOSE_PROMPT", "US_CLOSE_QUESTION", "FREE_TEXT_FORMAT"},
}
for rel, keys in targets.items():
    p = root / rel
    assert p.is_file() and not p.is_symlink(), "missing:" + rel
    source = p.read_text(encoding="utf-8")
    module = ast.parse(source)
    print("LIVE_FILE", rel, "SHA256", hashlib.sha256(source.encode()).hexdigest(), "LINES", len(source.splitlines()), flush=True)
    found = set()
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in keys:
                    value = ast.literal_eval(node.value)
                    print("CONFIG", rel, target.id, repr(value), flush=True)
                    found.add(target.id)
        if isinstance(node, ast.FunctionDef) and node.name in {"_generate", "analyze_news", "_prompt", "build_model_news"}:
            snippet = ast.get_source_segment(source, node)
            print("FUNCTION", rel, node.name, snippet[:14500], flush=True)
    print("CONFIG_KEYS_PRESENT", rel, sorted(found), flush=True)
print("LIVE_AI_READ_ONLY_INSPECTION_COMPLETE", flush=True)
