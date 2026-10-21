"""Read-only: print exact deployed files in recoverable chunks (no secrets)."""
from pathlib import Path
import base64,hashlib
root=Path("/opt/gaemigtp-news/app")
for f in ("backend/services/news_feed.py","ops/staged_daily_groq_issues.py"):
    data=(root/f).read_bytes()
    print("CONTENT_START "+f+" "+hashlib.sha256(data).hexdigest()+" "+str(len(data)),flush=True)
    b=base64.b64encode(data).decode("ascii")
    for j in range(0,len(b),3000):
        print("CONTENT_PIECE "+f+" "+str(j//3000)+" "+b[j:j+3000],flush=True)
    print("CONTENT_END "+f,flush=True)
