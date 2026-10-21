"""Read-only stock-direction and original-article coverage check on DigitalOcean."""
import json, os, sys, re
from datetime import datetime, timezone
sys.path.insert(0, "/opt/gaemigtp-news/app")
import psycopg
from backend.services.news_detail import read_selected_article_details
from backend.providers.market_price import fetch_kr_stock_quote

database_url = os.environ.get("NEWS_DATABASE_URL") or os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("NO_NEON_READ_URL")
targets = {
    "삼성전자": ("005930", [3,5,7,8,15,16,19,20,21,23]),
    "HT로보틱스": ("396300", [1,2,3,4,5,6,7,8,9,10,14]),
}
for stock,(symbol,positions) in targets.items():
    with psycopg.connect(database_url, connect_timeout=8) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("""
                SELECT checked_at, a.ord, a.obj
                FROM public.news_processed_snapshots s,
                  LATERAL jsonb_array_elements(s.result_payload->'paired_news_items') WITH ORDINALITY a(obj,ord)
                WHERE market='국내' AND stock_name=%s AND a.ord = ANY(%s)
                ORDER BY a.ord
            """,(stock,positions))
            rows=cursor.fetchall()
    quote=fetch_kr_stock_quote(symbol)
    print("STOCK "+stock+" QUOTE="+repr(quote)+" ARTICLES="+str(len(rows)),flush=True)
    for start in range(0,len(rows),3):
        batch=rows[start:start+3]
        details=read_selected_article_details([row[2] for row in batch],limit=3,with_sources=True)
        for (checked,ord_num,item),detail in zip(batch,details):
            body=str(detail.get("text") or "")
            excerpts=[]
            for part in re.split(r"(?<=[.!?])\\s+",body):
                if any(token in part.casefold() for token in ("삼성전자","외국인","자사주","매입","하이닉스","메가특구","로봇","ht로보틱스","투자경고","정밀부품","시장점유율","코어팀","양산","ess")):
                    snippets=re.sub(r"\\s+"," ",part).strip()[:200]
                    if snippets and snippets not in excerpts:
                        excerpts.append(snippets)
                if len(excerpts)>=2:break
            print("ITEM "+json.dumps({
                "stock":stock,"position":ord_num,"title":str(item.get("title") or "")[:120],
                "at":item.get("published_at"),"current_relation":item.get("relation_type"),
                "current_keywords":item.get("storyboard_keywords"),
                "source":detail.get("source"),"full_chars":len(body),
                "evidence":excerpts,
            },ensure_ascii=False),flush=True)
print("READ_ONLY_ARTICLE_AUDIT_DONE",flush=True)
