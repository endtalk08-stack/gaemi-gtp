import importlib.util,unittest,sys,types,os
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
spec=importlib.util.spec_from_file_location('store',Path('/opt/gaemigtp-news/app/backend/services/news_processed_store.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
cat=types.ModuleType('backend.analysis.news.catalog');cat.canonical_us_news_name=lambda x:x
sys.modules['backend.analysis.news.catalog']=cat
pg=types.ModuleType('psycopg.types.json');pg.Jsonb=lambda x:x
sys.modules['psycopg.types.json']=pg
class Cursor:
 def __init__(self, rows=(),one=None): self.rows=rows;self.one=one;self.sql=[];self.rowcount=0
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def execute(self,q,args=None):self.sql.append((q,args))
 def fetchone(self):return self.one
 def fetchall(self):return self.rows
 def cursor(self):return self
class Tests(unittest.TestCase):
 def setUp(self):m._invalidate_snapshot_cache()
 def test_cached_payload_isolation_and_expiry(self):
  with patch.dict(os.environ,{'NEWS_DATABASE_URL':'test','GAEMIGTP_NEWS_WORKER':'0'}),patch.object(m,'_read_snapshot_uncached',return_value=({'issue_briefs':[{'headline':'original'}]},2)) as fetch,patch.object(m.time,'monotonic',side_effect=[100,101,103,103]):
   x=m.read_snapshot('A',market='미국');x['issue_briefs'][0]['headline']='changed'
   self.assertEqual(m.read_snapshot('A',market='미국')['issue_briefs'][0]['headline'],'original')
   m.read_snapshot('A',market='미국');self.assertEqual(fetch.call_count,2)
 def test_worker_never_uses_read_cache(self):
  with patch.dict(os.environ,{'NEWS_DATABASE_URL':'test','GAEMIGTP_NEWS_WORKER':'1'}),patch.object(m,'_read_snapshot_uncached',return_value=({},30)) as f:
   m.read_snapshot('A',market='미국');m.read_snapshot('A',market='미국');self.assertEqual(f.call_count,2)
 def test_missing_result_not_cached(self):
  with patch.dict(os.environ,{'NEWS_DATABASE_URL':'test','GAEMIGTP_NEWS_WORKER':'0'}),patch.object(m,'_read_snapshot_uncached',return_value=(None,0)) as f:
   m.read_snapshot('A',market='미국');m.read_snapshot('A',market='미국');self.assertEqual(f.call_count,2)
 def test_signature_validates_owner_and_revision(self):
  d=dict(_title_only_revision=3,_kr_selection_revision=1,_code_source_revision=20,_company_match_revision=2,_event_taxonomy_revision=1,_issue_selection_revision=2,issue_briefs=[{'stock_names':['A']}])
  c=Cursor(one=('fingerprint',d))
  with patch.object(m,'_connect',return_value=c):
   self.assertEqual(m.read_signature('A','미국',50,3,'Asia/Seoul'),'fingerprint')
   d['issue_briefs']=[{'stock_names':['B']}];self.assertIsNone(m.read_signature('A','미국',50,3,'Asia/Seoul'))
   d['issue_briefs']=[];d['_code_source_revision']=19;self.assertIsNone(m.read_signature('A','미국',50,3,'Asia/Seoul'))
  self.assertNotIn('SELECT source_fingerprint, result_payload FROM',c.sql[0][0])
 def test_cleanup_keeps_fresh_sources_and_merges_only_changes(self):
  now=datetime.now(timezone.utc)
  fresh={'headline':'keep','source_articles':[{'published_at':(now-timedelta(hours=1)).isoformat()},{'published_at':(now-timedelta(hours=25)).isoformat()}]}
  stale={'headline':'remove','source_articles':[{'published_at':(now-timedelta(hours=25)).isoformat()}]}
  c=Cursor(rows=[('미국','A',50,3,'Asia/Seoul',{'issue_briefs':[fresh,stale]})])
  with patch.object(m,'_connect',return_value=c):m.purge_expired()
  updates=[(q,a) for q,a in c.sql if 'UPDATE public.news_processed_snapshots' in q]
  self.assertEqual(len(updates),1);q,a=updates[0]
  self.assertIn('result_payload=result_payload || %s',q)
  self.assertEqual([x['headline'] for x in a[0]['issue_briefs']],['keep'])
  self.assertEqual(len(a[0]['issue_briefs'][0]['source_articles']),1)
  self.assertNotIn('display_timezone, result_payload',c.sql[0][0])
 def test_cleanup_no_rewrite_when_unchanged(self):
  now=datetime.now(timezone.utc)
  c=Cursor(rows=[('미국','A',50,3,'Asia/Seoul',{'issue_briefs':[{'source_articles':[{'published_at':now.isoformat()}]}]})])
  with patch.object(m,'_connect',return_value=c):m.purge_expired()
  self.assertFalse(any('UPDATE public.news_processed_snapshots' in q for q,_ in c.sql))
 def test_invalid_source_dates_remain_filtered(self):
  self.assertEqual(m._retained_24h_issue_briefs([{'source_articles':[{'published_at':'nonsense'}]}],now=datetime.now(timezone.utc)),[])
if __name__=='__main__':
 import subprocess
 state=subprocess.run(['systemctl','is-active','gaemigtp-news.service'],capture_output=True,text=True)
 print('NEWS_SERVICE_STATE='+state.stdout.strip(),flush=True)
 assert state.stdout.strip()=='inactive', 'news collection must remain stopped'
 unittest.main()

