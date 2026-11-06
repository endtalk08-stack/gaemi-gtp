import sys
from pathlib import Path
sys.path.insert(0, "/opt/gaemigtp-news/app")

from backend.providers import tradingview_news_bundle
from backend.services.tradingview_news_page import build_snapshot

sample=[
 {"id":"s1","title":"Apple earnings beat estimates","published":1,"news_categories":["stock"],"relatedSymbols":[{"symbol":"NASDAQ:AAPL"}]},
 {"id":"m1","title":"Fed Powell signals rate cut path","published":1,"news_categories":["economic"]},
 {"id":"m2","title":"Nasdaq futures rise before open","published":1,"news_categories":["index","futures"]},
 {"id":"m3","title":"10-year Treasury yield jumps","published":1,"news_categories":["economic"]},
 {"id":"m4","title":"VIX jumps as investor sentiment weakens","published":1,"news_categories":["index"]},
]
snap=build_snapshot(sample, generated_at="test")
print("IMPORT_OK categories="+",".join(tradingview_news_bundle.CATEGORIES))
print("SNAP_COUNT="+str(snap["count"]))
print("SNAP_CODES="+",".join(x["event_category"]["code"] for x in snap["items"]))
