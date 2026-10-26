"""Read-only live news-worker control flow: rank ordering and refresh cadence."""
from pathlib import Path
p=Path("/opt/gaemigtp-news/app/backend/news_worker.py")
lines=p.read_text().splitlines()
for st,en in ((1,80),(82,132),(133,300)):
 print("WORKER_WINDOW "+str(st)+"-"+str(en),flush=True)
 for i in range(st-1,min(en,len(lines))):
  row=lines[i]
  if any(x in row.upper() for x in ("PASSWORD","TOKEN","SECRET","API_KEY","DATABASE_URL","AUTHORIZATION","NEWS_DATABASE")):
   row="[redacted configuration line]"
  print(str(i+1)+": "+row[:220],flush=True)
print("READ_ONLY_CADENCE_DONE",flush=True)

for filename in ("/opt/gaemigtp-news/app/backend/services/us_top20_rotation.py","/var/tmp/gaemigtp-news-top20-rotation.json"):
 p=Path(filename)
 print("ROTATION_FILE",p.name,flush=True)
 if p.is_file():
  for i,row in enumerate(p.read_text().splitlines()):
   if not any(x in row.upper() for x in ("PASSWORD","TOKEN","SECRET","API_KEY","DATABASE_URL","AUTHORIZATION")):
    print("ROTATION",i+1,row[:2500],flush=True)
