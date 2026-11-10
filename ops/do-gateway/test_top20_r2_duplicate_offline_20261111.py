"""Offline TOP20 metadata idempotence regression test. No network or DB writes."""
import datetime as dt
import json
from unittest.mock import patch

from backend.services import us_top20_metadata_sync as m
from backend.services import r2_news_uploader

class Cursor:
    def __init__(self): self.commands=[]
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def execute(self,sql,args=None):
        self.commands.append(sql.strip())
    def fetchone(self): return (3,20)
    def fetchall(self): return [('NVDA','ND','반도체')]
class Conn:
    def __init__(self): self.cursor_value=Cursor(); self.commits=0
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def cursor(self): return self.cursor_value
    def commit(self): self.commits+=1

now=dt.datetime(2026,11,10,22,20,tzinfo=dt.timezone.utc)
rows=[{'rank':i,'symbol':'S'+str(i),'name':'Stock '+str(i),
       'exchange':'ND','trading_value':i*1000,'volume':i*10}
      for i in range(1,21)]
snapshot={'captured_at':'2026-11-10T22:00:00+00:00','items':rows}
conn=Conn()
called=[]
def check_upload(path,*,object_key):
    assert object_key=='stocks/us/instruments.json'
    payload=json.loads(path.read_text(encoding='utf-8'))
    assert payload['items']==[{'symbol':'NVDA','exchange':'ND','industry':'반도체'}]
    called.append(1)
    return True
with patch.object(m,'read_top20',return_value=snapshot),\
     patch.object(m.psycopg,'connect',return_value=conn),\
     patch.object(r2_news_uploader,'upload_file',side_effect=check_upload),\
     patch.dict(m.os.environ,{'R2_ACCESS_KEY_ID':'test','R2_SECRET_ACCESS_KEY':'test'}):
    result=m.sync_once_after_close('postgresql://unused',now=now)
assert result=='already_saved_today_r2_updated',result
assert conn.commits==1
assert not any('INSERT INTO' in statement for statement in conn.cursor_value.commands)
assert len(called)==1
print('TOP20_R2_REGRESSION=pass; daily duplicate causes zero DB writes and one R2 update',flush=True)
