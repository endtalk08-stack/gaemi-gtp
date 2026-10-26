"""Read-only live NVDA verification; output counts and field availability only."""
import sys
sys.path.insert(0,"/opt/gaemigtp-news/app")
import os,json,psycopg,re
from collections import Counter
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 conn.execute("SET TRANSACTION READ ONLY")
 with conn.cursor() as cur:
  cur.execute("SELECT stock_name,result_payload FROM public.news_processed_snapshots WHERE market='미국' AND stock_name IN ('엔비디아','NVIDIA') AND expires_at>now()")
  for name,p in cur.fetchall():
   issues=p.get("_code_issue_briefs") or []
   urls=[str(s.get("url") or "") for b in issues for s in b.get("source_articles") or [] if isinstance(s,dict)]
   print("NVDA_LIVE_CHECK",json.dumps({"stock":name,"revision":p.get("_code_source_revision"),"raw_article_mode":p.get("_simple_news_revision"),"code_issues":len(issues),"ai_issues":len(p.get("_ai_issue_briefs") or []),"display_issues":len(p.get("issue_briefs") or []),"paired_articles":len(p.get("paired_news_items") or []),"panel_articles":len(p.get("panel_news_items") or []),"selected_articles":len(p.get("storyboard_news_items") or []),"issues_without_tags":sum(not b.get("tags") for b in issues),"english_only_titles":sum(not re.search("[가-힣]",str(b.get("headline") or "")) for b in issues),"english_only_summaries":sum(not re.search("[가-힣]",str(b.get("summary") or "")) for b in issues),"duplicate_source_occurrences":sum(n-1 for u,n in Counter(urls).items() if u)},ensure_ascii=False),flush=True)
