"""Read-only inspection of stock issue selection and AI eligibility; no API/DB calls."""
from pathlib import Path
import re
root=Path('/opt/gaemigtp-news/app/backend')
needles=('analyze news funnel','outside_approved_21','preserved_recent_issues','keyword_pass=','selected=','briefs=','news-ai','_select_stock_news','source reserve')
matches=[]
for p in root.rglob('*.py'):
 try:
  content=p.read_text(encoding='utf-8').splitlines()
 except Exception: continue
 for i,line in enumerate(content):
  if any(x in line for x in needles):
   matches.append((p.relative_to(root).as_posix(),i,content))
print('MATCHES='+str(len(matches)),flush=True)
seen=set()
for path,i,lines in matches[:28]:
 key=(path,i)
 if key in seen:continue
 seen.add(key)
 print('===',path,'line',i+1,'===',flush=True)
 for j in range(max(0,i-8),min(len(lines),i+12)):
  v=lines[j]
  if re.search('KEY|PASSWORD|TOKEN|SECRET|DATABASE_URL',v,re.I): continue
  print(str(j+1)+':'+v[:220],flush=True)
