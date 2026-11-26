"""Stop only the requested background collectors on the DO worker."""
import subprocess

UNITS = [
    "gaemigtp-tradingview-news.service",
    "gaemigtp-kiwoom-us-chart-bootstrap.service",
    "gaemigtp-kiwoom-us-daily.service",
]

for unit in UNITS:
    print("STOP_REQUEST=" + unit, flush=True)
    result = subprocess.run(
        ["systemctl", "stop", unit],
        check=False, capture_output=True, text=True, timeout=20,
    )
    if result.stdout.strip():
        print(result.stdout.strip(), flush=True)
    if result.stderr.strip():
        print(result.stderr.strip(), flush=True)
    print("EXIT_CODE=" + str(result.returncode), flush=True)
    if result.returncode != 0:
        raise SystemExit("STOP_FAILED=" + unit)

verify = subprocess.run(
    ["systemctl", "show", *UNITS, "--property=Id,ActiveState,SubState", "--no-pager"],
    check=False, capture_output=True, text=True, timeout=20,
)
print("=== VERIFY ===", flush=True)
print(verify.stdout.strip(), flush=True)
if verify.stderr.strip():
    print(verify.stderr.strip(), flush=True)
if verify.returncode != 0:
    raise SystemExit("VERIFY_FAILED")
