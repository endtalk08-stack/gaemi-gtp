"""Read-only rollback verification: no DB or server mutations."""
import ast, pathlib, sys, json
root=pathlib.Path("/opt/gaemigtp-news/app/backend/services")
for name in ("issue_briefs.py","news_result.py"):
 s=(root/name).read_text()
 ast.parse(s)
 print("MODULE_CHECK "+json.dumps({"file":name,"experimental_refs":any(x in s for x in ("shared_v1_issue_titles","compact_issue_titles")),"domestic_bypass":'if market not in ("국내", "kr")' in s}),flush=True)
 assert "shared_v1_issue_titles" not in s and "compact_issue_titles" not in s
 assert 'if market not in ("국내", "kr")' not in s
for name in ("shared_v1_issue_titles.py","compact_issue_titles.py"):
 print("UNUSED_LEFTOVER "+name+"="+str((root/name).exists()),flush=True)
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.issue_briefs import build_issue_briefs
from backend.services.news_result import _sanitize_news_display_briefs
print("IMPORT_OK",flush=True)
import os,psycopg
db=os.getenv("NEWS_DATABASE_URL") or os.getenv("DATABASE_URL")
with psycopg.connect(db,connect_timeout=10) as conn:
 with conn.cursor() as cur:
  cur.execute("SET TRANSACTION READ ONLY")
  for stock in ("삼성전자","SK하이닉스","삼성전기"):
   cur.execute("SELECT checked_at,result_payload FROM public.news_processed_snapshots WHERE market='국내' AND stock_name=%s ORDER BY checked_at DESC LIMIT 1",(stock,))
   row=cur.fetchone()
   if row:
    briefs=(row[1] or {}).get("issue_briefs") or []
    print("SNAPSHOT "+json.dumps({"stock":stock,"checked":str(row[0]),"headlines":[x.get("headline") for x in briefs],"issue_count":len(briefs)},ensure_ascii=False),flush=True)
print("ROLLBACK_READONLY_VERIFY_PASS",flush=True)
