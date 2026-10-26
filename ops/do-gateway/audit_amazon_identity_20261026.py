"""Read-only US identity diagnosis; no provider/AI calls or database writes."""
import json, inspect
from backend.services.news_identity_registry import resolve_us_news_identity
from backend.services import news_result
from backend.analysis.news.scoring import build_connected_keyword_test
for name,symbol in [("아마존닷컴","AMZN"),("아마존","AMZN"),("메타 플랫폼스(페이스북)","META")]:
 identity=resolve_us_news_identity(name,symbol=symbol)
 print("IDENTITY",json.dumps({"input":name,**identity},ensure_ascii=False),flush=True)
 for selected in [name,identity["news_name"]]:
  row=build_connected_keyword_test([{"title":"아마존, AWS 데이터센터 투자 확대","description":"아마존이 클라우드 데이터센터 투자를 확대한다고 발표했다."}],selected)["articles"][0]
  print("OWNER_PROBE",selected,json.dumps({k:row.get(k) for k in ["event_owner","relation_type","keywords"]},ensure_ascii=False),flush=True)
print("INSTALLED_BUILD_START",inspect.getsource(news_result.build_stock_news_result)[:1600],flush=True)
import os,psycopg
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 with conn.cursor() as cur:
  cur.execute("SELECT symbol,display_name,news_name,company_key,identity_status FROM public.market_instruments WHERE market='US' AND (symbol LIKE 'AMZN%' OR display_name LIKE '아마존%')")
  print("AMAZON_DB_ROWS",repr(cur.fetchall()),flush=True)
  cur.execute("SELECT stock_name,checked_at, jsonb_array_length(COALESCE(result_payload->'_code_issue_briefs','[]'::jsonb)),result_payload->>'_code_source_revision' FROM public.news_processed_snapshots WHERE market='미국' AND stock_name LIKE '아마존%'")
  print("AMAZON_SNAPSHOTS",repr(cur.fetchall()),flush=True)
