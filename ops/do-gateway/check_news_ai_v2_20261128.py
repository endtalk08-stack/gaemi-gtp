"""Read-only: confirm the deployed AI article job version, unit timeout and next run."""
import datetime as dt
import hashlib
import pathlib
import subprocess
import sys

sys.path.insert(0, "/opt/gaemigtp-news/app")
raw = pathlib.Path("/opt/gaemigtp-news/app/backend/us_news_ai_daily.py").read_bytes()
print("JOB_BLOB " + hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(), flush=True)
import backend.us_news_ai_daily as job
print("PACE %s HEADLINE_IN_SCHEMA %s NONE_TYPE %s" % (
    job.PACE_SECONDS, "headline" in job.RESPONSE_SCHEMA["schema"]["required"],
    "none" in job.RESPONSE_SCHEMA["schema"]["properties"]["type"]["enum"]), flush=True)
monday = dt.datetime(2026, 11, 30, 15, 30, tzinfo=dt.timezone.utc)
print("MONDAY_TRADING_DAY %s PREVIOUS_CLOSE %s" % (job.us_trading_day(monday), job.previous_close(monday).isoformat()), flush=True)
print(subprocess.run(["systemctl", "show", "gaemigtp-us-news-ai.service", "-p", "TimeoutStartUSec"],
                     text=True, capture_output=True).stdout.strip(), flush=True)
print(subprocess.run(["systemctl", "list-timers", "gaemigtp-us-news-ai.timer", "--all", "--no-pager", "--no-legend"],
                     text=True, capture_output=True).stdout.strip(), flush=True)
