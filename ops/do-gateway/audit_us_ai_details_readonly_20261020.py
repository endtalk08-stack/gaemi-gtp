"""Read-only US AI eligibility, funnel and output analysis; no provider or DB calls."""
from pathlib import Path
root=Path('/opt/gaemigtp-news/app')
ranges={'ops/staged_ai_sequential_batch.py':[(1,65),(110,235)],
'ops/staged_auto_ai_daily.py':[(1,155)],
'ops/staged_daily_groq_issues.py':[(1,105),(105,230)],
'ops/staged_ai_snapshot_integration.py':[(1,195)]}
for name,blocks in ranges.items():
 p=root/name
 print('FILE',name,'exists',p.exists(),flush=True)
 if not p.exists():continue
 lines=p.read_text().splitlines()
 for lo,hi in blocks:
  print('RANGE',lo,hi,flush=True)
  for i in range(lo-1,min(hi,len(lines))):
   row=lines[i]
   if '.groq_api_key' in row or 'os.environ' in row: continue
   print(str(i+1)+':'+row[:220],flush=True)
