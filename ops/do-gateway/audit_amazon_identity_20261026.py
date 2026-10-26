"""Explicitly approved US identity/status/count output to existing GitHub admin logs. Read-only."""
import sys
sys.path.insert(0,"/opt/gaemigtp-news/app")
import os,json,psycopg
from backend.services.news_identity_registry import resolve_us_news_identity
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 conn.execute("SET TRANSACTION READ ONLY")
 with conn.cursor() as cur:
  cur.execute("SELECT symbol,display_name,news_name,identity_status FROM public.market_instruments WHERE market='US' AND is_active=true ORDER BY symbol")
  rows=cur.fetchall()
  for symbol,name,news,status in rows:
   by_symbol=resolve_us_news_identity(name,symbol=symbol)
   by_name=resolve_us_news_identity(name)
   cur.execute("SELECT stock_name,jsonb_array_length(COALESCE(result_payload->'_code_issue_briefs','[]'::jsonb)),jsonb_array_length(COALESCE(result_payload->'_ai_issue_briefs','[]'::jsonb)) FROM public.news_processed_snapshots WHERE market='미국' AND stock_name=ANY(%s) AND expires_at>now()",(by_symbol["snapshot_names"],))
   print("US_MATCH_CHECK",json.dumps({"symbol":symbol,"name":name,"db_news_name":news,"db_status":status,"symbol_match":by_symbol["news_name"],"symbol_status":by_symbol["status"],"worker_name_match":by_name["news_name"],"worker_name_status":by_name["status"],"issue_counts":cur.fetchall()},ensure_ascii=False),flush=True)
