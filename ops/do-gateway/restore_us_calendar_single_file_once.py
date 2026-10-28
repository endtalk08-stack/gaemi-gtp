"""One-time, hash-pinned rollback of mistakenly deployed calendar source only.

Runs as the existing unprivileged gaemigtp-news user.
No database, external API, service, environment, or other file touched.
"""
import hashlib
import os
from pathlib import Path
import stat
import sys

TARGET = Path("/opt/gaemigtp-news/app/backend/us_market_calendar.py")
EXPECTED_GIT_BLOB = "a72569b9dea9da073e37954fdd473d2394165a92"

if not TARGET.exists() and not TARGET.is_symlink():
    print("CALENDAR_ALREADY_ABSENT")
    sys.exit(0)
metadata = TARGET.lstat()
if not stat.S_ISREG(metadata.st_mode):
    print("CALENDAR_UNEXPECTED_FILE_TYPE_NO_CHANGE")
    sys.exit(2)
raw = TARGET.read_bytes()
digest = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()
if digest != EXPECTED_GIT_BLOB:
    print("CALENDAR_HASH_MISMATCH_NO_CHANGE")
    sys.exit(3)
print("CALENDAR_HASH_VERIFIED")
try:
    TARGET.unlink()
except PermissionError:
    print("CALENDAR_DELETE_PERMISSION_DENIED_NO_CHANGE")
    sys.exit(4)
if TARGET.exists() or TARGET.is_symlink():
    print("CALENDAR_DELETE_NOT_CONFIRMED")
    sys.exit(5)
print("CALENDAR_FILE_REMOVED_VERIFIED")
