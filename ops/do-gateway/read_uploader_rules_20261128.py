"""Read-only: print the R2 key rules and function names of the deployed uploader (no secrets)."""
import pathlib, re
src = pathlib.Path("/opt/gaemigtp-news/app/backend/services/r2_news_uploader.py").read_text(encoding="utf-8")
for n, line in enumerate(src.splitlines(), 1):
    if re.search(r"fullmatch|object_key ==|object_key !=|startswith\(|^def |ALLOWED|KEY", line) and "environ" not in line:
        print("L%d %s" % (n, line.rstrip()[:220]), flush=True)
