"""Read only trace of CURRENT US-only AI worker vs legacy shared KR/US pipelines."""
from pathlib import Path
import re
root=Path('/opt/gaemigtp-news/app')
for rel in ['backend/news_worker.py','ops/staged_ai_sequential_batch.py','ops/staged_auto_ai_daily.py','backend/services/news_result.py']:
 p=root/rel
 print('FILE',rel,'exists',p.exists(),flush=True)
 if not p.exists():continue
 lines=p.read_text(encoding='utf-8').splitlines()
 words=('def apply_worker_ai','def apply_unchanged_worker_ai','def process_due_ai_snapshots','outside_approved_21','approved_21','market ==','market in','market not in','market !=','US','미국','ai_model','groq','selected_issues','issue_briefs')
 hits=[i for i,x in enumerate(lines) if any(w in x for w in words)]
 print('MATCH_COUNT',len(hits),flush=True)
 for i in hits[:65]:
  v=lines[i].strip()
  if re.search(r'(key|token|secret|password|database_url)\s*=',v,re.I):continue
  print(f'{i+1}: {v[:210]}',flush=True)
