"""Publish the saved company intros to R2 (news/ai/us/PROFILES.json). No AI call."""
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys

APP = "/opt/gaemigtp-news/app"
EXPECTED_BLOB = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("EXPECTED_BLOB", "")
sys.path.insert(0, APP)
raw = pathlib.Path(APP, "backend/us_news_ai_daily.py").read_bytes()
blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
print("JOB_BLOB " + blob, flush=True)

for line in pathlib.Path("/var/lib/gaemigtp-news/r2.env").read_text(encoding="utf-8").splitlines():
    m = re.match(r"^(?:export\s+)?(R2_[A-Z_]+)\s*=\s*(.*)$", line.strip())
    if m:
        value = m.group(2).strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ[m.group(1)] = value

import backend.us_news_ai_daily as job
if not hasattr(job, "publish_profiles"):
    print("OLD_JOB_VERSION", flush=True)
    raise SystemExit(2)
ai = job.read_state(job.STATE_PATH).get("profiles") or {}
manual = job.read_manual_intros()
count = job.publish_profiles(ai, manual, dt.datetime.now(dt.timezone.utc))
print("PUBLISHED %d (ai=%d manual=%d)" % (count, len(ai), len(manual)), flush=True)
for symbol, text in sorted(job.intro_map(ai, manual).items()):
    print("INTRO %s %s" % (symbol, text), flush=True)
