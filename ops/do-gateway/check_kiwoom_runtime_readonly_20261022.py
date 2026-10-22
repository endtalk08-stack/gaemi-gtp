"""Offline-only read-only Kiwoom runtime dependency check (no keys, no HTTP)."""
import importlib.util
import sys
from pathlib import Path

print("KIWOOM_RUNTIME_PYTHON=" + str(sys.version_info.major) + "." + str(sys.version_info.minor), flush=True)
print("KIWOOM_RUNTIME_REQUESTS_INSTALLED=" + str(importlib.util.find_spec("requests") is not None).lower(), flush=True)
print("KIWOOM_RUNTIME_KIWOOM_ENV_PRESENT=" + str(Path("/etc/gaemigtp/kiwoom.env").is_file()).lower(), flush=True)
print("KIWOOM_RUNTIME_PROBE_PRESENT=" + str(Path("/opt/gaemigtp-news/app/backend/kiwoom_probe.py").is_file()).lower(), flush=True)
