"""Inspect AI wiring by reading source only; no imports, DB or provider calls."""
import ast, os
from pathlib import Path
root=Path('/opt/gaemigtp-news/app')
print('INTERVAL_SECONDS',os.environ.get('NEWS_WORKER_INTERVAL_SECONDS','300(default)'))
for rel in ('ops/staged_ai_sequential_batch.py','ops/staged_auto_ai_daily.py','ops/staged_daily_issue_schedule.py','ops/staged_daily_groq_issues.py'):
 p=root/rel
 print('FILE',rel,'PRESENT',p.is_file())
 if not p.is_file(): continue
 source=p.read_text('utf8'); lines=source.splitlines(); tree=ast.parse(source)
 for n in tree.body:
  if isinstance(n,ast.FunctionDef) and n.name in ('apply_worker_ai','process_due_ai_snapshots','scheduled_kst_time','build_model_news','analyze_news'):
   print('FUNCTION',n.name)
   for line in lines[n.lineno-1:n.end_lineno]: print(line)
 for n in tree.body:
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('MODEL','PROMPT') for t in n.targets):
   print(ast.get_source_segment(source,n))
print('READ_ONLY_AI_AUDIT_DONE')
