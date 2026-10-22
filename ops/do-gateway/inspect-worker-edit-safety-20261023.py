"""Read-only production worker source and provider call sites; no credentials."""
import hashlib
from pathlib import Path
root=Path('/opt/gaemigtp-news/app')
for rel in ('backend/news_worker.py','backend/services/news_feed.py','backend/providers/naver_news.py','backend/providers/official_company_news.py','backend/providers/sec_filings.py'):
 p=root/rel
 print('=== SOURCE',rel,'present',p.is_file(),flush=True)
 if not p.is_file():continue
 s=p.read_text('utf-8')
 print('SHA256',hashlib.sha256(s.encode()).hexdigest(),'LINES',len(s.splitlines()),flush=True)
 if rel=='backend/news_worker.py':
  print('=== WORKER_SOURCE_BEGIN',flush=True)
  print(s,flush=True)
  print('=== WORKER_SOURCE_END',flush=True)
 elif rel=='backend/services/news_feed.py':
  ls=s.splitlines()
  for n in range(max(0,next((i for i,l in enumerate(ls) if l.startswith('def fetch_stock_news(')),len(ls))-2),len(ls)):
   print('FEED',n+1,ls[n][:220],flush=True)
  for n,l in enumerate(ls):
   if 'naver_news.search_news' in l or l.startswith('def _fetch_query(') or l.startswith('def _fetch_queries('):
    print('NAVER_CALL',n+1,' | '.join(x.strip()[:160] for x in ls[max(0,n-3):min(len(ls),n+5)]),flush=True)
 elif rel.endswith('naver_news.py'):
  for n,l in enumerate(s.splitlines()):
   if l.startswith('def ') or 'requests.get' in l or 'urlopen(' in l:
    print('PROVIDER',n+1,l[:200],flush=True)
print('INSPECTION_DONE',flush=True)
