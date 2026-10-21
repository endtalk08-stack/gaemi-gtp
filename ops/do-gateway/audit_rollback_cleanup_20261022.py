"""Read-only cleanup permission and duplicates audit."""
import os, pathlib, json, pwd, grp, subprocess, psycopg, sys
root=pathlib.Path("/opt/gaemigtp-news/app/backend/services")
print("USER",os.geteuid(),pwd.getpwuid(os.geteuid()).pw_name,flush=True)
for name in ("shared_v1_issue_titles.py","compact_issue_titles.py"):
 p=root/name
 if p.exists():
  st=p.stat(); d=p.parent.stat()
  print("LEFTOVER",json.dumps({"name":name,"owner":pwd.getpwuid(st.st_uid).pw_name,"mode":oct(st.st_mode&0o777),"directory_owner":pwd.getpwuid(d.st_uid).pw_name,"directory_mode":oct(d.st_mode&0o777),"writable_directory":os.access(p.parent,os.W_OK),"writable_file":os.access(p,os.W_OK)}),flush=True)
 else:print("ALREADY_ABSENT",name,flush=True)
for p in root.glob("*.py"):
 try:s=p.read_text()
 except:continue
 if any(q in s for q in ("shared_v1_issue_titles","compact_issue_titles")):
  print("REFERENCE",p.name,flush=True)
db=os.getenv("NEWS_DATABASE_URL") or os.getenv("DATABASE_URL")
with psycopg.connect(db,connect_timeout=10) as c:
 with c.cursor() as q:
  q.execute("SET TRANSACTION READ ONLY")
  for stock in ("삼성전자","SK하이닉스","삼성전기","HT로보틱스","두산에너빌리티","삼성SDI","대한광통신","한화오션"):
   q.execute("SELECT checked_at,result_payload FROM public.news_processed_snapshots WHERE market='국내' AND stock_name=%s ORDER BY checked_at DESC LIMIT 1",(stock,))
   row=q.fetchone()
   if row is None:print("STOCK_MISSING",stock,flush=True);continue
   p=row[1] or {}
   items=p.get("paired_news_items") or []
   briefs=p.get("issue_briefs") or []
   titles=[str(x.get("headline") or "") for x in briefs]
   urls=[str(x.get("url") or x.get("link") or "") for x in items]
   nonempty=[u for u in urls if u]
   print("STOCK",json.dumps({"stock":stock,"checked":str(row[0]),"items":len(items),"url_duplicates":len(nonempty)-len(set(nonempty)),"issue_count":len(titles),"duplicate_headlines":len(titles)-len(set(titles)),"titles":titles},ensure_ascii=False),flush=True)
print("AUDIT_FINISHED",flush=True)
