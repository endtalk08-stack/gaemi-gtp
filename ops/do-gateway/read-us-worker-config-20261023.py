"""Read only safe worker scheduling settings (no credentials, API or DB calls)."""
import os
import ast
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

configured=os.environ.get('NEWS_WORKER_STOCKS','')
entries=[s.strip() for s in configured.split(',') if s.strip()]
print('NEWS_WORKER_CONFIGURED_COUNT',len(entries),flush=True)
print('NEWS_WORKER_CONFIGURED_ORDER_BEGIN',flush=True)
for idx,name in enumerate(entries,1):
    print(idx,name[:90],flush=True)
print('NEWS_WORKER_CONFIGURED_ORDER_END',flush=True)
print('NEWS_WORKER_INTERVAL_SECONDS',os.environ.get('NEWS_WORKER_INTERVAL_SECONDS','(default 300)'),flush=True)
print('NEWS_WORKER_RANKING_URL_IS_DEFAULT',os.environ.get('NEWS_WORKER_RANKING_URL','https://gaemi-gtp.onrender.com')=='https://gaemi-gtp.onrender.com',flush=True)
base=Path('/opt/gaemigtp-news/app/ops')
for name in ['staged_ai_issue_display_adapter.py','staged_daily_groq_issues.py','staged_daily_issue_schedule.py']:
    p=base/name
    print('SOURCE',name,'PRESENT',p.is_file(),flush=True)
    if p.is_file():
        tree=ast.parse(p.read_text('utf8'))
        for node in tree.body:
            if isinstance(node,ast.FunctionDef) and (name=='staged_ai_issue_display_adapter.py' or node.name in ('scheduled_kst_time','build_model_news','recent_ai_articles')):
                print('FUNCTION',name,node.name,flush=True)
                for line in ast.get_source_segment(p.read_text('utf8'),node).splitlines()[:47]:
                    print('CODE',line[:200],flush=True)
print('KST_NOW',datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'),flush=True)
print('READONLY_CONFIG_DONE',flush=True)
