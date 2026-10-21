"""One stock smoke of existing worker save path, no extra AI or other changes."""
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.news_worker import process_stock
from ops.staged_daily_issue_schedule import scheduled_kst_time
import os
import psycopg

stock="TSMC ADR"
now=datetime.now(ZoneInfo("Asia/Seoul"))
us_date=now.astimezone(ZoneInfo("America/New_York")).date()
due=scheduled_kst_time(us_date)
if now >= due:
    print("NEON_SMOKE_SKIPPED=AI_WINDOW_ACTIVE",flush=True)
    raise SystemExit(0)

db=os.environ.get("NEWS_DATABASE_URL") or os.environ.get("DATABASE_URL")
if not db:
    raise RuntimeError("neon_url_missing")
def snapshot():
    with psycopg.connect(db,connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT checked_at,expires_at,
                jsonb_array_length(COALESCE(result_payload->'paired_news_items','[]'::jsonb)),
                jsonb_array_length(COALESCE(result_payload->'issue_briefs','[]'::jsonb))
                FROM public.news_processed_snapshots
                WHERE market='미국' AND stock_name=%s AND result_limit=50
                  AND storyboard_limit=3 AND display_timezone='Asia/Seoul'
                  LIMIT 1""",(stock,))
            return cur.fetchone()
print("BEFORE="+repr(snapshot()),flush=True)
result=process_stock("미국",stock)
print("PROCESS_RESULT="+str(result),flush=True)
after=snapshot()
print("AFTER="+repr(after),flush=True)
print("NEON_SNAPSHOT_VERIFIED="+str(bool(after and after[2]>0)),flush=True)
