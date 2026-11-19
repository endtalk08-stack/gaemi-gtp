"""Read-only systemd wiring check for Kiwoom services. Never prints environment values."""
import subprocess
units = [
 "gaemigtp-kiwoom-us-top20-api.service",
 "gaemigtp-kiwoom-us-top20-https.service",
 "gaemigtp-kiwoom-us-value.service",
 "gaemigtp-kiwoom-us-daily.service",
 "gaemigtp-kiwoom-us-chart-bootstrap.service",
]
for unit in units:
    p=subprocess.run(["systemctl","show",unit,"--no-pager",
      "-p","LoadState","-p","ActiveState","-p","SubState","-p","User",
      "-p","Group","-p","ExecStart","-p","EnvironmentFiles"],
      capture_output=True,text=True,timeout=8)
    print("UNIT_BEGIN",unit,flush=True)
    print((p.stdout or "").strip()[:3000],flush=True)
    print("UNIT_END",flush=True)
print("SAFE_ENV_NAME_CHECK_BEGIN",flush=True)
# Only list variable names from process environment; never values.
import os
for name in sorted(os.environ):
    if any(k in name.upper() for k in ("KIWOOM","GAEMI","APP_KEY","APP_SECRET")):
        print("ENV_NAME",name,flush=True)
print("SAFE_ENV_NAME_CHECK_END",flush=True)
