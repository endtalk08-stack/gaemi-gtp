"""Read only news detail integration and schedule; never call news API or write cache."""
from __future__ import annotations
import pathlib,os,json,subprocess,sys
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.providers import tradingview_news_bundle as bundle
from backend.providers import tradingview_news_detail as detail
from backend.services import tradingview_news_page as page
print("NEWS_AUDIT_BEGIN=1")
print("NEWS_SOURCE_FILE="+str(pathlib.Path(bundle.__file__)))
print("NEWS_BASIC_WINDOWS="+json.dumps(bundle.BASIC_COLLECTION_WINDOWS))
print("NEWS_MODE_VARIABLE_PRESENT="+str("TRADINGVIEW_NEWS_MODE" in os.environ))
print("NEWS_DETAIL_BUDGET_PRESENT="+str("NEWS_DETAIL_REQUEST_BUDGET" in os.environ))
print("NEWS_DETAIL_PUBLISH_FLAG_PRESENT="+str("NEWS_DETAIL_PUBLICATION_ALLOWED" in os.environ))
print("NEWS_DETAIL_AUTOMATIC="+str("enrich_articles(" in pathlib.Path("/opt/gaemigtp-news/app/backend/tradingview_news_worker.py").read_text()))
cache=bundle.CACHE_PATH
if cache.is_file() and not cache.is_symlink():
 try:
  obj=json.loads(cache.read_text(encoding="utf-8"))
  rows=obj.get("items",[])
  if not isinstance(rows,list):rows=[]
  print("CACHE_ITEM_COUNT="+str(len(rows)))
  print("CACHE_DETAIL_BODY_COUNT="+str(sum(bool(x.get("detail_body")) for x in rows if isinstance(x,dict))))
  print("CACHE_DETAIL_CHECKED_COUNT="+str(sum(bool(x.get("detail_checked")) for x in rows if isinstance(x,dict))))
  print("CACHE_LAST_SLOT="+str(obj.get("last_slot","")))
  print("CACHE_MODE="+str(obj.get("mode","")))
  print("CACHE_FEED_VERSION="+str(obj.get("feed_version","")))
 except Exception as exc: print("CACHE_READ_ERROR="+type(exc).__name__)
else:print("CACHE_PRESENT=False")
for unit in ("gaemigtp-news.service","gaemigtp-tradingview-news.service","gaemigtp-tradingview-news.timer"):
 p=subprocess.run(["systemctl","is-active",unit],capture_output=True,text=True)
 q=subprocess.run(["systemctl","is-enabled",unit],capture_output=True,text=True)
 print("UNIT="+unit+" ACTIVE="+p.stdout.strip()+" ENABLED="+q.stdout.strip())
print("NEWS_AUDIT_END=1")
