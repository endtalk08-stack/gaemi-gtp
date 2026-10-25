"""One-off, read-only capture of exact installed news logic and cache."""
from pathlib import Path
import base64
import hashlib

base = Path("/opt/gaemigtp-news/app")
targets = {
    "result": base / "backend/services/news_result.py",
    "store": base / "backend/services/news_processed_store.py",
    "feed": base / "backend/services/news_feed.py",
}
for key, path in targets.items():
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("SOURCE_UNAVAILABLE_" + key)
    data = path.read_bytes()
    print("GAEMI_FILE_META", key, hashlib.sha256(data).hexdigest(), len(data), flush=True)
    encoded = base64.b64encode(data).decode("ascii")
    for index in range(0, len(encoded), 1600):
        print("GAEMI_SOURCE_CHUNK", key, index // 1600, encoded[index:index + 1600], flush=True)
    print("GAEMI_SOURCE_END", key, flush=True)
