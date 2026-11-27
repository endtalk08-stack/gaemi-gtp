"""Read-only: confirm the daily AI analysis timer, its next run, and the job module."""
import subprocess
import sys

sys.path.insert(0, "/opt/gaemigtp-news/app")
print(subprocess.run(["systemctl", "list-timers", "gaemigtp-us-news-ai.timer", "--all", "--no-pager"],
                     text=True, capture_output=True).stdout, flush=True)
for unit in ("gaemigtp-us-news-ai.timer", "gaemigtp-us-news-ai.service"):
    out = subprocess.run(["systemctl", "show", unit, "-p", "ActiveState", "-p", "UnitFileState", "-p", "LoadState"],
                         text=True, capture_output=True).stdout.replace("\n", " ")
    print("UNIT %s %s" % (unit, out), flush=True)
import backend.us_news_ai_daily as job
import datetime as dt
print("MODULE_OK model=%s pace=%s" % (job.MODEL, job.PACE_SECONDS), flush=True)
print("TODAY_NY_TRADING_DAY=%s" % job.us_trading_day(), flush=True)
nxt = dt.datetime(2026, 11, 27, 15, 30, tzinfo=dt.timezone.utc)
print("NEXT_RUN_TRADING_DAY=%s" % job.us_trading_day(nxt), flush=True)
