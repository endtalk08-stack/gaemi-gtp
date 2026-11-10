"""Offline unit smoke checks for the deployed metadata module, no DB/API writes."""
import ast
import subprocess
from pathlib import Path

root=Path("/opt/gaemigtp-news/app")
module=root/"backend/services/us_top20_metadata_sync.py"
if not module.is_file() or module.is_symlink():
    raise RuntimeError("metadata_module_missing")
ast.parse(module.read_text(encoding="utf-8"))
print("US_META_SYNTAX=pass",flush=True)

script = r"""
import datetime as dt
from zoneinfo import ZoneInfo
from backend.services.us_top20_metadata_sync import _valid_source
now = dt.datetime(2026,11,10,22,0,tzinfo=dt.timezone.utc)
rows = [dict(rank=i,symbol='S'+str(i),name='Stock '+str(i),exchange='ND',trading_value=i*10.0) for i in range(1,21)]
good = dict(items=rows,captured_at='2026-11-10T21:05:01+00:00')
assert _valid_source(good,now) is not None
assert _valid_source(dict(items=rows,captured_at='2026-11-09T21:05:01+00:00'),now) is None
assert _valid_source(dict(items=rows[:-1],captured_at=good['captured_at']),now) is None
assert _valid_source(good,dt.datetime(2026,11,10,19,0,tzinfo=dt.timezone.utc)) is None
print('US_META_VALIDATION=pass')
"""
result=subprocess.run(("/opt/gaemigtp-news/venv/bin/python","-c",script),cwd=str(root),capture_output=True,text=True,timeout=20)
print(result.stdout.strip(),flush=True)
if result.returncode!=0:
    print("US_META_VALIDATION=failed",flush=True)
    print("US_META_VALIDATION_KIND=" + ("ModuleNotFoundError" if "ModuleNotFoundError" in result.stderr else "other"),flush=True)
    raise SystemExit(1)
