"""One-off approved integration verification: existing TOP20 -> Neon read -> R2 PUT.

Never invokes Kiwoom or the daily chart collector. Never inserts DB rows.
Uses existing protected runtime credentials; prints statuses only.
"""
import os
import re
import sys
from pathlib import Path
sys.path.insert(0, "/opt/gaemigtp-news/app")

path=Path("/var/lib/gaemigtp-news/r2.env")
try:
    lines=path.read_text(encoding="utf-8").splitlines()
except OSError as exc:
    print("R2_VERIFY_ENV_ERROR="+type(exc).__name__,flush=True)
    raise SystemExit(2)
for line in lines:
    m=re.match(r"^(?:export\s+)?(R2_ACCESS_KEY_ID|R2_SECRET_ACCESS_KEY)\s*=\s*(.*)$",line.strip())
    if m:
        value=m.group(2).strip()
        if len(value)>1 and value[0]==value[-1] and value[0] in ("'",'"'):
            value=value[1:-1]
        os.environ[m.group(1)]=value
if not all(os.getenv(k) for k in ("R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","NEWS_DATABASE_URL")):
    print("R2_VERIFY_CREDENTIALS=missing",flush=True)
    raise SystemExit(3)

import psycopg
from backend.services.us_top20_metadata_sync import sync_once_after_close

dsn=os.environ["NEWS_DATABASE_URL"]
sql="""SELECT count(*) FROM public.market_rank_snapshots
        WHERE market='US' AND rank_type='trading_value'"""
with psycopg.connect(dsn, connect_timeout=7) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
        before=cur.fetchone()[0]
print("R2_VERIFY_SNAPSHOT_COUNT_BEFORE="+str(before),flush=True)
result=sync_once_after_close(dsn)
print("R2_VERIFY_RESULT="+str(result),flush=True)
with psycopg.connect(dsn, connect_timeout=7) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
        after=cur.fetchone()[0]
print("R2_VERIFY_SNAPSHOT_COUNT_AFTER="+str(after),flush=True)
if result!="already_saved_today_r2_updated" or before!=after:
    raise SystemExit(4)
print("R2_VERIFY_PASS=yes",flush=True)
