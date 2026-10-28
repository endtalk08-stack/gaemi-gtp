"""Read-only source audit: no database/network/module imports."""
import ast,json,pathlib
base=pathlib.Path('/opt/gaemigtp-news/app')
paths=['backend/news_worker.py','backend/services/news_processed_store.py','backend/services/news_result.py','backend/services/news_metadata_store.py','ops/staged_auto_ai_daily.py','ops/staged_ai_sequential_batch.py','ops/staged_news_processed_store.py']
for rel in paths:
 p=base/rel
 if not p.is_file(): continue
 src=p.read_text(); print('FILE',rel)
 tree=ast.parse(src)
 for n in ast.walk(tree):
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
   block=ast.get_source_segment(src,n) or ''
   if any(s in block for s in ['SELECT ','read_signature','purge_expired','read_snapshot','process_due_ai_snapshots']):
    if len(block)<23000: print(block)
    else:
     for s in ast.walk(n):
      if isinstance(s,ast.Constant) and isinstance(s.value,str) and 'SELECT ' in s.value: print('SQL',n.name,s.value)
 print('END_FILE')
