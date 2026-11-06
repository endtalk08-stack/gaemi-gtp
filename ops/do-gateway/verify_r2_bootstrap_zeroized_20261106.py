from pathlib import Path
p=Path("/opt/gaemigtp-news/app/backend/r2-bootstrap.enc")
print("R2_BOOTSTRAP_EXISTS=" + ("yes" if p.exists() else "no"))
print("R2_BOOTSTRAP_BYTES=" + (str(p.stat().st_size) if p.exists() else "0"))
