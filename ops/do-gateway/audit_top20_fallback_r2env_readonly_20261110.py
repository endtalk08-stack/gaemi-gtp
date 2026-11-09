"""Read-only check of frozen TOP20 fallback and existing optional R2 env file.

Reports no credential values and performs no network, DB, service or file writes.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path

root=Path("/var/lib/gaemigtp-news")
state_path=root/"rotation.json"
r2_path=root/"r2.env"
print("TOP20_FALLBACK_AUDIT_BEGIN=1")
if state_path.is_file() and not state_path.is_symlink():
    try:
        state=json.loads(state_path.read_text(encoding="utf-8"))
        rows=state.get("cycle")
        valid=(isinstance(rows,list) and len(rows)==20)
        if valid:
            ranks=[r.get("rank") for r in rows if isinstance(r,dict)]
            symbols=[str(r.get("symbol") or "").upper() for r in rows if isinstance(r,dict)]
            names=[str(r.get("name") or r.get("display_name") or "").strip() for r in rows if isinstance(r,dict)]
            valid=(len(ranks)==20 and set(ranks)==set(range(1,21))
                   and len(set(symbols))==20
                   and all(re.fullmatch(r"[A-Z][A-Z0-9.\\-]{0,15}",sym) for sym in symbols)
                   and all(names))
        print("FROZEN_CYCLE_VALID="+str(bool(valid)))
        print("FROZEN_CYCLE_ITEMS="+str(len(rows) if isinstance(rows,list) else 0))
        index=state.get("next_index")
        print("FROZEN_CYCLE_NEXT_INDEX="+str(index))
        pending=state.get("pending")
        print("FROZEN_CYCLE_PENDING="+str(bool(pending)))
        can_resume=(bool(valid) and type(index) is int and 0<=index<=20
                    and (not pending or (index<20 and pending==rows[index]["symbol"])))
        print("FROZEN_CYCLE_FALLBACK_PLAN_OK="+str(can_resume))
    except (OSError,ValueError,TypeError) as exc:
        print("ROTATION_READ_ERROR="+type(exc).__name__)
else:
    print("ROTATION_STATE_UNAVAILABLE=True")
print("R2_ENV_FILE_EXISTS="+str(r2_path.is_file()))
print("R2_ENV_FILE_SYMLINK="+str(r2_path.is_symlink()))
print("R2_ENV_FILE_READABLE="+str(os.access(r2_path,os.R_OK)))
if r2_path.is_file() and not r2_path.is_symlink() and os.access(r2_path,os.R_OK):
    # Read only environment variable NAMES; never parse or print values.
    try:
        keys=set()
        for line in r2_path.read_text(encoding="utf-8").splitlines():
            text=line.strip()
            if text.startswith("export "): text=text[7:].strip()
            if not text or text.startswith("#") or "=" not in text: continue
            keys.add(text.split("=",1)[0].strip())
        for key in ("R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","R2_ACCOUNT_ID"):
            print("R2_ENV_HAS_"+key+"="+str(key in keys))
    except (OSError,UnicodeError) as exc:
        print("R2_ENV_READ_ERROR="+type(exc).__name__)
print("TOP20_FALLBACK_AUDIT_END=1")
