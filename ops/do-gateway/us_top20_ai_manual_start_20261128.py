#!/usr/bin/env python3
"""Launch the existing US TOP20 AI pipeline as a detached systemd unit.

This does not change application code or the normal daily timer. It reuses the
installed service's exact runtime, environment files, user, and sandbox, adding
only --force for this explicitly requested one-time verification run.
"""
import subprocess
import sys

SERVICE = "gaemigtp-us-news-ai.service"
UNIT = "gaemigtp-us-news-ai-manual-20261128.service"

def active(unit):
    return subprocess.run(
        ["systemctl", "is-active", "--quiet", unit],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0

if active(SERVICE):
    print("REFUSED: regular US TOP20 AI service is already active", flush=True)
    sys.exit(2)
if active(UNIT):
    print("REFUSED: manual US TOP20 AI test is already active", flush=True)
    sys.exit(2)

cmd = [
    "systemd-run", "--no-block", "--unit=gaemigtp-us-news-ai-manual-20261128",
    "--description=One-time manual verification of the existing US trading-value TOP20 AI pipeline",
    "--property=Type=oneshot",
    "--property=User=gaemigtp-news",
    "--property=Group=gaemigtp-news",
    "--property=WorkingDirectory=/opt/gaemigtp-news/app",
    "--property=EnvironmentFile=/etc/gaemigtp/news-worker.env",
    "--property=EnvironmentFile=/var/lib/gaemigtp-news/r2.env",
    "--property=Environment=PYTHONUNBUFFERED=1",
    "--property=Environment=PYTHONDONTWRITEBYTECODE=1",
    "--property=TimeoutStartSec=7800",
    "--property=NoNewPrivileges=true",
    "--property=PrivateTmp=true",
    "--property=ProtectSystem=strict",
    "--property=ProtectHome=true",
    "--property=ReadWritePaths=/var/lib/gaemigtp-news",
    "/opt/gaemigtp-news/venv/bin/python",
    "-m", "backend.us_news_ai_daily", "--force",
]
result = subprocess.run(cmd, text=True, capture_output=True)
if result.returncode:
    print("LAUNCH_FAILED rc=%d" % result.returncode, flush=True)
    if result.stdout:
        print(result.stdout, flush=True)
    if result.stderr:
        print(result.stderr, flush=True)
    sys.exit(result.returncode)
print("LAUNCHED existing TOP20 AI pipeline; unit=" + UNIT, flush=True)
if result.stdout:
    print(result.stdout, flush=True)
if result.stderr:
    print(result.stderr, flush=True)
