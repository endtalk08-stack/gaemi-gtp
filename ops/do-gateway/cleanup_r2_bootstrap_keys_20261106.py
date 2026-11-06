from pathlib import Path
for raw in (
    "/var/lib/gaemigtp-news/r2-bootstrap-key.pem",
    "/var/lib/gaemigtp-news/r2-bootstrap-key.pub.pem",
):
    p=Path(raw)
    if p.exists() or p.is_symlink():
        p.unlink()
print("R2_BOOTSTRAP_KEYS_REMOVED")
