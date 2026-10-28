import pathlib,json,ast,subprocess
base=pathlib.Path('/opt/gaemigtp-news/app')
paths=['backend/kiwoom_us_price_relay.py','backend/kiwoom_us_live_prices.py','backend/kiwoom_us_value_collector.py','backend/kiwoom_us_daily_collector.py']
for rel in paths:
 p=base/rel
 if not p.exists(): continue
 source=p.read_text();print('FILE='+rel)
 tree=ast.parse(source)
 for n in tree.body:
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name not in ('signing_key',):
   print(ast.get_source_segment(source,n))
  elif isinstance(n,ast.Assign):
   names=[x.id for x in n.targets if isinstance(x,ast.Name)]
   if any(x in ('SQL','SOURCE') for x in names):print(ast.get_source_segment(source,n))
units=['gaemigtp-kiwoom-us-fe.service','gaemigtp-kiwoom-us-daily.service','gaemigtp-kiwoom-us-value.service','gaemigtp-kiwoom-us-daily.timer','gaemigtp-kiwoom-us-value.timer','gaemigtp-news.service']
for unit in units:
 print('UNIT='+unit)
 print(subprocess.run(['systemctl','show',unit,'-p','ActiveState','-p','SubState','-p','UnitFileState','-p','NextElapseUSecRealtime','-p','NextElapseUSecMonotonic'],capture_output=True,text=True).stdout)
 p=pathlib.Path('/etc/systemd/system')/unit
 if p.is_file():
  for line in p.read_text().splitlines():
   if line.startswith(('OnCalendar=','OnBootSec=','OnUnitActiveSec=','OnUnitInactiveSec=','Persistent=')):print(line)
