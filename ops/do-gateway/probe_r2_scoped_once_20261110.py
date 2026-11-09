"""One-time scoped R2 credential probe; uses only a disposable object.
Never starts services, touches Neon, or logs secrets.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import hmac
import os
import subprocess
import uuid
from pathlib import Path
from urllib.parse import quote
import requests

ENV = Path("/var/lib/gaemigtp-news/r2.env")
ACCOUNT = "6cf7450897a598809db421965a07304b"
BUCKET = "gaemigtp-news-data"
UNIT = "gaemigtp-news.service"
HOST = ACCOUNT + ".r2.cloudflarestorage.com"

def show(prop):
    p = subprocess.run(["systemctl", "show", UNIT, "--property=" + prop, "--value"],
                       capture_output=True, text=True, timeout=15, check=True)
    return p.stdout.strip()

active = show("ActiveState")
enabled = show("UnitFileState")
envfiles = show("EnvironmentFiles")
print("R2_PROBE_NEWS_SERVICE_ACTIVE=" + active, flush=True)
print("R2_PROBE_NEWS_SERVICE_ENABLED=" + enabled, flush=True)
print("R2_PROBE_UNIT_ENV_LINKED=" + str("r2.env" in envfiles), flush=True)
if active != "inactive" or enabled != "disabled" or "r2.env" not in envfiles:
    raise SystemExit("R2_PROBE_ABORT_UNEXPECTED_UNIT_STATE")
if not ENV.is_file() or ENV.is_symlink():
    raise SystemExit("R2_PROBE_ENV_MISSING_OR_SYMLINK")
print("R2_PROBE_ENV_PRESENT=True", flush=True)
mode = ENV.stat().st_mode & 0o777
print("R2_PROBE_ENV_MODE_0600=" + str(mode == 0o600), flush=True)
if mode != 0o600:
    raise SystemExit("R2_PROBE_ABORT_PERMISSIONS")
values = {}
for raw in ENV.read_text(encoding="utf-8").splitlines():
    if "=" in raw:
        key, value = raw.split("=", 1)
        if key in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            values[key] = value.strip()
if not all(values.get(k) for k in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")):
    raise SystemExit("R2_PROBE_ENV_CREDENTIALS_MISSING")
print("R2_PROBE_CREDENTIALS_PRESENT=True", flush=True)

access = values["R2_ACCESS_KEY_ID"]
secret = values["R2_SECRET_ACCESS_KEY"]
key = "_gaemi_verification/r2-probe-" + uuid.uuid4().hex + ".txt"
uri = "/" + BUCKET + "/" + "/".join(quote(s, safe="-_.~") for s in key.split("/"))
url = "https://" + HOST + uri
payload = b"gaemi-r2-scoped-verification-v1"
created = False

def sign(key_bytes, message):
    return hmac.new(key_bytes, message.encode(), hashlib.sha256).digest()

def request(method, body=b""):
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    digest = hashlib.sha256(body).hexdigest()
    canonical_headers = "host:" + HOST + "\nx-amz-content-sha256:" + digest + "\nx-amz-date:" + stamp + "\n"
    signed = "host;x-amz-content-sha256;x-amz-date"
    canonical = "\n".join((method, uri, "", canonical_headers, signed, digest))
    scope = date + "/auto/s3/aws4_request"
    to_sign = "\n".join(("AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()))
    kd = sign(("AWS4" + secret).encode(), date)
    kr = sign(kd, "auto")
    ks = sign(kr, "s3")
    kf = sign(ks, "aws4_request")
    signature = hmac.new(kf, to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = "AWS4-HMAC-SHA256 Credential=" + access + "/" + scope + ", SignedHeaders=" + signed + ", Signature=" + signature
    return requests.request(method, url, data=body if method == "PUT" else None,
                            headers={"Authorization": authorization, "Host": HOST,
                                     "x-amz-content-sha256": digest, "x-amz-date": stamp},
                            timeout=20)

try:
    response = request("PUT", payload)
    print("R2_PROBE_PUT_HTTP=" + str(response.status_code), flush=True)
    if response.status_code not in (200, 201, 204):
        raise RuntimeError("PUT_DENIED")
    created = True
    response = request("GET")
    print("R2_PROBE_GET_HTTP=" + str(response.status_code), flush=True)
    if response.status_code != 200 or response.content != payload:
        raise RuntimeError("GET_VERIFY_FAILED")
    print("R2_PROBE_READ_MATCH=True", flush=True)
finally:
    if created:
        response = request("DELETE")
        print("R2_PROBE_DELETE_HTTP=" + str(response.status_code), flush=True)
        if response.status_code not in (200, 204):
            raise RuntimeError("TEMP_OBJECT_CLEANUP_FAILED")
if not created:
    raise SystemExit("R2_PROBE_NOT_CREATED")
print("R2_PROBE_SUCCESS_TEMP_OBJECT_REMOVED", flush=True)
