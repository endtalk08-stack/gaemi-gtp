"""Read-only DigitalOcean droplet capacity diagnostics.

Collects point-in-time CPU, memory, disk, process and service health.
Does not read environment variables, credentials, application data, or modify state.
"""
import subprocess

COMMANDS = [
    ("TIME_AND_LOAD", ["bash", "-lc", "date -Is; uptime; cat /proc/loadavg"]),
    ("MEMORY", ["free", "-h"]),
    ("DISK_SPACE", ["df", "-hT", "/", "/opt/gaemigtp-news"]),
    ("DISK_INODES", ["df", "-i", "/", "/opt/gaemigtp-news"]),
    ("TOP_PROCESSES", ["bash", "-lc", "ps -eo pid,comm,%cpu,%mem,rss --sort=-%mem | head -n 16"]),
    ("FAILED_UNITS", ["systemctl", "--failed", "--no-pager"]),
    ("SERVICE_RESOURCE_STATE", [
        "systemctl", "show",
        "gaemigtp-kiwoom-us-top20-api.service",
        "gaemigtp-kiwoom-us-top20-https.service",
        "gaemigtp-tradingview-news.service",
        "gaemigtp-news.service",
        "--property=Id,ActiveState,SubState,CPUUsageNSec,MemoryCurrent,MemoryPeak,NRestarts",
        "--no-pager",
    ]),
    ("NETWORK_SUMMARY", ["ss", "-s"]),
]

for label, command in COMMANDS:
    print("\n=== " + label + " ===", flush=True)
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=12
        )
        output = (result.stdout or "") + (result.stderr or "")
        print(output[:12000].strip() or "(no output)", flush=True)
        print("EXIT_CODE=" + str(result.returncode), flush=True)
    except Exception as exc:
        print("CHECK_ERROR=" + type(exc).__name__ + ": " + str(exc), flush=True)
