"""Read-only: git blob hashes of files about to be replaced."""
import hashlib, pathlib
for rel in ("backend/services/r2_news_uploader.py", "backend/us_macro_news.py"):
    p = pathlib.Path("/opt/gaemigtp-news/app", rel)
    if not p.exists():
        print("BLOB %s missing" % rel, flush=True); continue
    raw = p.read_bytes()
    print("BLOB %s %s" % (rel, hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()), flush=True)
