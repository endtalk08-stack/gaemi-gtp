from __future__ import annotations
import datetime as dt, hashlib, hmac, os, sys
from pathlib import Path
from urllib.parse import quote
import requests

ACCOUNT_ID="6cf7450897a598809db421965a07304b"
BUCKET="gaemigtp-news-data"
KEY="news/latest.json"
env_path=Path("/var/lib/gaemigtp-news/r2.env")
for raw in env_path.read_text(encoding="utf-8").splitlines():
    if raw and "=" in raw:
        k,v=raw.split("=",1)
        if k in {"R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY"}:
            os.environ[k]=v
access=os.environ.get("R2_ACCESS_KEY_ID","").strip()
secret=os.environ.get("R2_SECRET_ACCESS_KEY","").strip()
if not access or not secret:
    raise SystemExit("R2_ENV_MISSING")

def sign(key,msg):
    return hmac.new(key,msg.encode(),hashlib.sha256).digest()

now=dt.datetime.now(dt.timezone.utc)
amz=now.strftime("%Y%m%dT%H%M%SZ")
date=now.strftime("%Y%m%d")
host=f"{ACCOUNT_ID}.r2.cloudflarestorage.com"
uri=f"/{BUCKET}/"+"/".join(quote(x,safe="-_.~") for x in KEY.split("/"))
payload=hashlib.sha256(b"").hexdigest()
headers=f"host:{host}\nx-amz-content-sha256:{payload}\nx-amz-date:{amz}\n"
signed="host;x-amz-content-sha256;x-amz-date"
canon="\n".join(("GET",uri,"",headers,signed,payload))
scope=f"{date}/auto/s3/aws4_request"
tosign="\n".join(("AWS4-HMAC-SHA256",amz,scope,hashlib.sha256(canon.encode()).hexdigest()))
kd=sign(("AWS4"+secret).encode(),date)
kr=sign(kd,"auto")
ks=sign(kr,"s3")
kf=sign(ks,"aws4_request")
sig=hmac.new(kf,tosign.encode(),hashlib.sha256).hexdigest()
auth=f"AWS4-HMAC-SHA256 Credential={access}/{scope}, SignedHeaders={signed}, Signature={sig}"
r=requests.get(
    f"https://{host}{uri}",
    headers={"Authorization":auth,"Host":host,"x-amz-content-sha256":payload,"x-amz-date":amz},
    timeout=20,
)
print(f"R2_GET_STATUS={r.status_code}")
if r.status_code==200:
    print("R2_READ_OK")
else:
    code="unknown"
    try:
        import xml.etree.ElementTree as ET
        code=(ET.fromstring(r.text).findtext("Code") or "unknown").strip()
    except Exception:
        pass
    print(f"R2_READ_FAILED code={code}")
