"""Read-only US AI execution and visibility diagnosis. No DB or provider calls."""
from pathlib import Path
import ast
import subprocess
from collections import Counter
import re

root = Path('/opt/gaemigtp-news/app')
for rel in ('backend/news_worker.py','ops/staged_ai_sequential_batch.py','ops/staged_daily_issue_schedule.py',
            'ops/staged_daily_call_guard.py','ops/staged_ai_snapshot_integration.py',
            'ops/staged_ai_issue_store.py','backend/services/news_processed_store.py'):
    p = root / rel
    print('=== FILE',rel,'PRESENT',p.is_file(),flush=True)
    if not p.is_file(): continue
    source = p.read_text('utf-8')
    lines = source.splitlines()
    try: tree = ast.parse(source)
    except SyntaxError as exc:
        print('PARSE_ERROR',type(exc).__name__,flush=True);continue
    print('LINES',len(lines),'FUNCTIONS',[(x.name,x.lineno) for x in tree.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))],flush=True)
    if rel.endswith('news_worker.py'):
        for n,line in enumerate(lines,1):
            if n<=110 or any(k in line for k in
                ('STOCKS','stocks','stock_names','watchlist','market=','market ','rank','popul','trading',
                 'priority','sort','sleep','interval','while True','run_cycle','for stock','for market',
                 'apply_worker_ai','apply_unchanged_worker_ai','process_due_ai_snapshots',
                 'fetch_stock','get_stock','save_snapshot','NEWS_UNIVERSE')):
                lo=max(1,n-2);hi=min(len(lines),n+2)
                print('CODE',rel,lo,':',' | '.join(str(j)+':'+lines[j-1].strip()[:175] for j in range(lo,hi+1)),flush=True)
    else:
        if rel.endswith('news_processed_store.py'):
            terms=('def save_snapshot','def mark_checked','INSERT INTO','UPDATE public','processed_at','checked_at','_ai_issue_briefs','source_fingerprint')
        else:
            terms=('def ','exchange_day','scheduled_kst_time','reserve_once','request_hash','display_time',
                   'to_issue_briefs','source_articles','snapshot','result_payload','WHERE market','status')
        wanted=set()
        for n,line in enumerate(lines,1):
            if any(term in line for term in terms):
                wanted.update(range(max(1,n-1),min(len(lines),n+1)+1))
        for n in sorted(wanted):
            print('CODE',rel,n,lines[n-1][:195],flush=True)

print('=== SERVICE')
proc=subprocess.run(['systemctl','show','gaemigtp-news.service','-p','ExecStart','-p','User','-p','ActiveState'],
                    capture_output=True,text=True,timeout=10)
print(proc.stdout[:1600],flush=True)

print('=== JOURNAL_US_AI_RECENT')
try:
    proc=subprocess.run(['journalctl','-u','gaemigtp-news.service','--since','2026-10-22 14:15:00 UTC',
        '--until','2026-10-22 22:30:00 UTC','--no-pager','-o','short-iso'],
        capture_output=True,text=True,timeout=15)
    records=proc.stdout.splitlines()
    c=Counter();stock_events=[];ai_events=[]
    for line in records:
        if '[news-ai]' in line:
            ai_events.append(line.strip()[:280])
        if '[news-worker]' in line and 'market=미국' in line:
            stock_events.append(line.strip()[:250])
            m=re.search(r'stock=([^ ]+)',line)
            if m:c[m.group(1)]+=1
    print('LOG_TOTAL',len(records),'US_STOCK_EVENTS',len(stock_events),'AI_EVENTS',len(ai_events),flush=True)
    print('STOCK_EVENTS_FIRST_90',flush=True)
    for line in stock_events[:90]:print(line,flush=True)
    print('STOCK_EVENTS_LAST_35',flush=True)
    for line in stock_events[-35:]:print(line,flush=True)
    print('AI_EVENTS_FIRST_95',flush=True)
    for line in ai_events[:95]:print(line,flush=True)
    print('AI_EVENTS_LAST_35',flush=True)
    for line in ai_events[-35:]:print(line,flush=True)
except Exception as exc:
    print('JOURNAL_ERROR',type(exc).__name__,flush=True)
print('READONLY_SCHEDULE_INSPECTION_DONE',flush=True)
