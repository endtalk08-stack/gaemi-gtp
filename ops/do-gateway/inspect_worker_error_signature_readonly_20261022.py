from pathlib import Path
import re
p=Path("/opt/gaemigtp-news/app/backend/news_worker.py")
s=p.read_text().splitlines()
for i,line in enumerate(s):
 if "build_stock_news_result(" in line or "error=" in line or "except Exception" in line:
  print("WORKER_CONTEXT "+str(i+1)+" "+repr("\\n".join(s[max(0,i-4):min(len(s),i+10)])),flush=True)
from backend.services.news_result import build_stock_news_result
import inspect
print("BUILD_SIGNATURE="+str(inspect.signature(build_stock_news_result)),flush=True)
