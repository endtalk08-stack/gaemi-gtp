from pathlib import Path

paths = [
    Path("/opt/gaemigtp-news/app/backend/r2-bootstrap.enc"),
    Path("/var/lib/gaemigtp-news/r2-bootstrap-key.pem"),
    Path("/var/lib/gaemigtp-news/r2-bootstrap-key.pub.pem"),
]
for p in paths:
    try:
        if p.exists() or p.is_symlink():
            p.unlink()
    except PermissionError:
        print(f"CLEANUP_PERMISSION_DENIED={p}")
        raise
print("R2_BOOTSTRAP_CLEANUP_OK")
