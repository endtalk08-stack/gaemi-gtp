"""User-approved read-only Amazon identity and issue-count check. No credentials output."""
import os,json,psycopg
from backend.services.news_identity_registry import resolve_us_news_identity
for name in ("아마존닷컴","아마존"):
 identity=resolve_us_news_identity(name,symbol="AMZN")
 print("AMAZON_MATCH",json.dumps({"input":name,"ticker":identity.get("ticker"),"news_name":identity.get("news_name"),"status":identity.get("status")},ensure_ascii=False),flush=True)
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 conn.execute("SET TRANSACTION READ ONLY")
 with conn.cursor() as cur:
  cur.execute("SELECT symbol,display_name,news_name,identity_status FROM public.market_instruments WHERE market='US' AND (symbol LIKE 'AMZN%' OR display_name LIKE '아마존%')")
  print("AMAZON_DB_MATCH",json.dumps(cur.fetchall(),ensure_ascii=False),flush=True)
  cur.execute("SELECT stock_name,jsonb_array_length(COALESCE(result_payload->'_code_issue_briefs','[]'::jsonb)),jsonb_array_length(COALESCE(result_payload->'_ai_issue_briefs','[]'::jsonb)) FROM public.news_processed_snapshots WHERE market='미국' AND stock_name LIKE '아마존%'")
  print("AMAZON_ISSUE_COUNTS",json.dumps(cur.fetchall(),ensure_ascii=False),flush=True)
