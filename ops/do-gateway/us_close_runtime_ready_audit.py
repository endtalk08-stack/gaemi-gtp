"""Bounded dry-run for staged US-close runtime on existing DigitalOcean. No AI/DB writes."""
import datetime as dt
import json
import sys
from zoneinfo import ZoneInfo
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.us_market_close_runtime import verified_originals,verified_indices
def main():
    day=dt.date(2026,10,19)
    print("US_RUNTIME_AUDIT_SCOPE=indices_plus_3_originals_for_oct19_nogroq_nowrites",flush=True)
    try:
        indices=verified_indices(day)
        print("US_RUNTIME_INDICES="+json.dumps(indices,ensure_ascii=False),flush=True)
        if len(indices)!=3:raise RuntimeError("index_count")
        try:
            verified_indices(dt.date(2026,10,16))
        except ValueError:
            print("US_RUNTIME_STALE_DATE_REJECTED",flush=True)
        else:raise RuntimeError("stale_date_accepted")
        articles=verified_originals(day,now_utc=dt.datetime(2026,10,20,10,30,tzinfo=ZoneInfo("Asia/Seoul")))
        for a in articles:
            print("US_RUNTIME_ARTICLE="+json.dumps({
                "title":a["title"],"url":a["url"],"publisher":a["publisher"],
                "published":a["published_at"],"body_chars":a["body_chars"],
                "category":a["group"]},ensure_ascii=False),flush=True)
        print("US_RUNTIME_ACCEPTED_COUNT="+str(len(articles)),flush=True)
        if len(articles)!=3:raise RuntimeError("insufficient_original_articles")
    except Exception as exc:
        print("US_RUNTIME_ERROR="+type(exc).__name__+":"+str(exc)[:80],flush=True)
        return 2
    print("US_RUNTIME_AUDIT_PASS",flush=True)
    return 0
if __name__=="__main__":sys.exit(main())
