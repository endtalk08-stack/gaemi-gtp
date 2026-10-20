"""Assess exact 07:00 KST original-only news readiness using existing runtime.
Read-only. No DB, no AI, no worker/timer changes.
"""
import datetime as dt,json,sys
from zoneinfo import ZoneInfo
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.us_market_close_runtime import verified_originals
DAY=dt.date(2026,10,19)
CUTOFF=dt.datetime(2026,10,20,7,0,tzinfo=ZoneInfo("Asia/Seoul"))
def main():
    print("US_CLOSE_0700_SCOPE=historical_cutoff_oct20_0700_3_naver_queries_max36_originals",flush=True)
    articles=verified_originals(DAY,now_utc=CUTOFF)
    print("US_CLOSE_0700_READY_COUNT="+str(len(articles)),flush=True)
    for a in articles:print("US_CLOSE_0700_ARTICLE="+json.dumps({"source":a["publisher"],"published_at":a["published_at"],"body_chars":a["body_chars"],"title":a["title"][:120]},ensure_ascii=False),flush=True)
    print("US_CLOSE_0700_AUDIT_COMPLETE",flush=True)
    return 0
if __name__=="__main__":sys.exit(main())
