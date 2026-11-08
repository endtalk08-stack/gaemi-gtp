"""Read-only effective environment check for the existing news worker.
The gateway injects the root-protected EnvironmentFile via systemd-run.
Never open or print the secret env file or API credentials.
"""
import os
import subprocess

def setting_status(name):
    value = os.environ.get(name)
    if value is None:
        return "MISSING"
    if name == "NEWS_DETAIL_REQUEST_BUDGET":
        try:
            n = int(value.strip())
        except ValueError:
            return "INVALID_NONINTEGER"
        return "ENABLED_POSITIVE" if n > 0 else "DISABLED_ZERO_OR_NEGATIVE"
    return "ENABLED" if value.strip() == "1" else "DISABLED_OR_INVALID"

print("NEWS_DETAIL_ENV_CHECK_START=1", flush=True)
for key in ("NEWS_DETAIL_REQUEST_BUDGET", "NEWS_DETAIL_PUBLICATION_ALLOWED"):
    print(key + "_STATUS=" + setting_status(key), flush=True)
# Presence only, never display or validate secret value.
print("TRADINGVIEW_API_KEY_PRESENT=" + str(bool(os.environ.get("TRADINGVIEW_API_KEY", "").strip())), flush=True)
for unit in ("gaemigtp-news.service", "gaemigtp-tradingview-news.service"):
    p = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=10)
    print("UNIT=" + unit + " STATE=" + p.stdout.strip(), flush=True)
print("NEWS_DETAIL_ENV_CHECK_DONE=1", flush=True)
