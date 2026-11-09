"""Read-only check of frozen TOP20 fallback and existing optional R2 env file.

Reports no credential values and performs no network, DB, service or file writes.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

root=Path("/var/lib/gaemigtp-news")
state_path=root/"rotation.json"
r2_path=root/"r2.env"
print("TOP20_FALLBACK_AUDIT_BEGIN=1")
if state_path.is_file() and not state_path.is_symlink():
    try:
        state=json.loads(state_path.read_text(encoding="utf-8"))
        rows=state.get("cycle")
        from backend.services.us_top20_rotation import normalize_ranking, plan_tick
        try:
            valid=normalize_ranking(rows)
            print("FROZEN_CYCLE_VALID=True")
            print("FROZEN_CYCLE_ITEMS="+str(len(valid)))
            print("FROZEN_CYCLE_NEXT_INDEX="+str(state.get("next_index")))
            try:
                selected,_=plan_tick(state, [])
                print("FROZEN_CYCLE_FALLBACK_PLAN_OK=True")
                print("FROZEN_CYCLE_FALLBACK_RANK="+str(selected.get("rank")))
            except (ValueError,TypeError) as exc:
                print("FROZEN_CYCLE_FALLBACK_PLAN_ERROR="+type(exc).__name__)
        except (ValueError,TypeError) as exc:
            print("FROZEN_CYCLE_VALID=False")
            print("FROZEN_CYCLE_ERROR="+str(exc)[:60])
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
