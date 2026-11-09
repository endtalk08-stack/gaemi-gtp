"""Only systemd metadata: discover protected Kiwoom env file paths, no contents."""
from __future__ import annotations
import subprocess
from pathlib import Path

for unit in (
 "gaemigtp-kiwoom-us-value.service",
 "gaemigtp-news.service",
 "gaemigtp-tradingview-news.service",
):
    print("UNIT="+unit,flush=True)
    for prop in ("ActiveState","UnitFileState","EnvironmentFiles","ExecStart","User"):
        value=subprocess.run(["systemctl","show",unit,"--property="+prop,"--value"],
           capture_output=True,text=True,timeout=12,check=True).stdout.strip()
        if prop=="EnvironmentFiles":
            # Paths are configuration metadata; never open or echo their values.
            print("ENV_FILE_PATHS="+value,flush=True)
            continue
        if prop=="ExecStart":
            # Avoid arguments that might include sensitive command-line strings.
            print("EXECSTART_CONFIGURED="+str(bool(value)),flush=True)
            continue
        print(prop+"="+value,flush=True)
print("KIWOOM_ENVIRONMENT_METADATA_READONLY=True",flush=True)
