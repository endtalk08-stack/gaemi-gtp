import hashlib, pathlib, subprocess
p = pathlib.Path("/opt/gaemigtp-news/app/backend/kiwoom_us_top20_api.py")
if not p.is_file() or p.is_symlink():
    raise SystemExit("LIVE_MODULE_FILE_MISSING_OR_UNSAFE")
sha = subprocess.check_output(["git", "hash-object", "--", str(p)], text=True).strip()
print("LIVE_MODULE_BLOB_SHA=" + sha)
for unit in ("gaemigtp-kiwoom-us-top20-api.service", "gaemigtp-kiwoom-us-top20-https.service"):
    result = subprocess.run(["systemctl", "is-active", unit], text=True, capture_output=True)
    print("SERVICE_" + unit.upper().replace("-", "_") + "=" + (result.stdout.strip() or "unknown"))
