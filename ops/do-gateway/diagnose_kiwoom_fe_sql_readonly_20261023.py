"""Read-only verification of deployed Kiwoom FE writer SQL and PostgreSQL binding.
Only displays hash, SQL field markers, EXPLAIN status and safe exception class.
No ticker/price/token/DSN displayed. No DB write.
"""
import os
import sys
import hashlib
from pathlib import Path
sys.path.insert(0, "/opt/gaemigtp-news/app")
p=Path("/opt/gaemigtp-news/app/backend/kiwoom_us_live_prices.py")
s=p.read_text()
print("FE_DEPLOYED_SHA256="+hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
print("FE_DEPLOYED_SQL_MARKERS="+repr({
  "typed_numeric": "%s::numeric IS NOT NULL" in s,
  "typed_text": "%s::text" in s,
  "write_guard": "IS DISTINCT FROM" in s,
  "batch_15": "previous_flush >= 15" in s,
}),flush=True)
import psycopg
db=os.environ.get("NEWS_DATABASE_URL","")
if not db:
    print("FE_EXPLAIN_ERROR=missing_db_url",flush=True)
    raise SystemExit(2)
sql="""EXPLAIN UPDATE public.market_rank_entries
   SET price=%s,
       change_rate=COALESCE(%s,change_rate),
       entry_payload=COALESCE(entry_payload,'{}'::jsonb)
            || jsonb_build_object('live_price_at',%s::text,'live_price_source','kiwoom:FE')
 WHERE snapshot_id=%s AND market='US' AND symbol=%s
   AND (price IS DISTINCT FROM %s OR
        (%s::numeric IS NOT NULL AND change_rate IS DISTINCT FROM %s::numeric))"""
try:
    with psycopg.connect(db,connect_timeout=6) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM public.market_rank_snapshots WHERE source='kiwoom' AND market='US' AND rank_type='trading_value' ORDER BY captured_at DESC,id DESC LIMIT 1")
            rec=cur.fetchone()
            if not rec:
                print("FE_EXPLAIN=no_snapshot",flush=True)
                raise SystemExit(3)
            cur.execute(sql,(200.0,1.5,"2026-10-23T00:00:00Z",rec[0],"NVDA",200.0,1.5,1.5))
            print("FE_EXPLAIN=PASS rows="+str(len(cur.fetchall())),flush=True)
except Exception as exc:
    print("FE_EXPLAIN_ERROR="+type(exc).__name__,flush=True)
    raise SystemExit(4)
