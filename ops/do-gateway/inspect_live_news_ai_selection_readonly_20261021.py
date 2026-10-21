"""Read-only inspect running worker news->AI call chain before scoped edit."""
from pathlib import Path
import ast,hashlib
ROOT=Path("/opt/gaemigtp-news/app")
TARGETS={
"backend/news_worker.py":("process_stock","run_once","next_ranked_stock"),
"backend/services/news_feed.py":("_fetch_queries","fetch_stock_news"),
"backend/services/news_result.py":("build_stock_news_result",),
"ops/staged_daily_groq_issues.py":("recent_ai_articles","build_model_news"),
"ops/staged_ai_sequential_batch.py":("apply_worker_ai","run_stock_batch"),
}
for path,names in TARGETS.items():
    f=ROOT/path
    print("FILE",path,"exists",f.is_file(),flush=True)
    if not f.is_file():continue
    s=f.read_text()
    print("SHA",hashlib.sha256(s.encode()).hexdigest(),"lines",len(s.splitlines()),flush=True)
    tree=ast.parse(s)
    lines=s.splitlines()
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names:
            chunk=lines[node.lineno-1:node.end_lineno]
            if path.endswith("news_result.py"):
                chunk=chunk[:115]+["[remaining omitted]"]
            if path.endswith("staged_ai_sequential_batch.py"):
                chunk=chunk[:85]+["[remaining omitted]"]
            print("FUNC",node.name,"line",node.lineno,"to",node.end_lineno,flush=True)
            for i,line in enumerate(chunk):
                print(str(i+node.lineno)+": "+line,flush=True)
print("INSPECTION_END",flush=True)
