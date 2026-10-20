"""Read-only configuration probe. Never display credential values."""
import json
import os
from pathlib import Path

names = ("GAEMI_KIWOOM_APP_KEY", "GAEMI_KIWOOM_APP_SECRET",
         "KIWOOM_APP_KEY", "KIWOOM_APP_SECRET",
         "KIWOOM_SECRET_KEY", "KIWOOM_SECRETKEY", "KIWOOM_APPKEY")
present = {name: bool(os.environ.get(name, "").strip()) for name in names}
separate = Path("/etc/gaemigtp/kiwoom.env")
print("KIWOOM_CONFIG_STATUS=" + json.dumps({
    "worker_env_key_names": [name for name, is_present in present.items() if is_present],
    "separate_file_exists": separate.is_file(),
    "separate_file_readable": os.access(separate, os.R_OK),
}, ensure_ascii=False), flush=True)
