"""Read-only verification of every stock in the actual worker's current 20-stock cycle."""
import sys,json,os,re,psycopg
from pathlib import Path
from collections import Counter
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.news_identity_registry import resolve_us_news_identity
state=json.loads(Path("/var/lib/gaemigtp-news/rotation.json").read_text())
print("TOP20_CURSOR",json.dumps({"cycle":state.get("cycle_number"),"next_index":state.get("next_index"),"pending":state.get("pending")}),flush=True)
with psycopg.connect(os.environ["NEWS_DATABASE_URL"],connect_timeout=10) as conn:
 conn.execute("SET TRANSACTION READ ONLY")
 with conn.cursor() as cur:
  for item in state.get("cycle",[]):
   name=item.get("name") or item.get("display_name")
   ident=resolve_us_news_identity(name,symbol=item.get("symbol"))
   names=list(dict.fromkeys([name]+ident["snapshot_names"]))
   cur.execute("SELECT stock_name,result_payload,checked_at,expires_at>now() FROM public.news_processed_snapshots WHERE market='미국' AND stock_name=ANY(%s) ORDER BY checked_at DESC",(names,))
   rows=cur.fetchall()
   exact=next((row for row in rows if row[0]==name),rows[0] if rows else None)
   out={"rank":item["rank"],"symbol":item["symbol"],"stock":name,"match":ident["status"],"snapshot":bool(exact)}
   if exact:
    p=exact[1];issues=p.get("_code_issue_briefs") or []
    urls=[s.get("url") for b in issues for s in b.get("source_articles") or [] if isinstance(s,dict) and s.get("url")]
    out.update({"saved_as":exact[0],"checked":str(exact[2]),"unexpired":exact[3],"revision":p.get("_code_source_revision"),"raw_article_mode":p.get("_simple_news_revision"),"issues":len(issues),"collected":len(p.get("paired_news_items") or []),"selected":len(p.get("storyboard_news_items") or []),"missing_tags":sum(not b.get("tags") for b in issues),"english_titles":sum(not re.search("[가-힣]",str(b.get("headline") or "")) for b in issues),"english_summaries":sum(not re.search("[가-힣]",str(b.get("summary") or "")) for b in issues),"duplicate_sources":sum(n-1 for n in Counter(urls).values() if n>1)})
   print("TOP20_RESULT",json.dumps(out,ensure_ascii=False),flush=True)
