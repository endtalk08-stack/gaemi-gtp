"""Upload news-page JSON to Cloudflare R2 using S3 SigV4.

No third-party AWS SDK is required. Credentials are read from environment only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import re
from pathlib import Path
from urllib.parse import quote

import requests
import xml.etree.ElementTree as ET

ACCOUNT_ID = "6cf7450897a598809db421965a07304b"
BUCKET = "gaemigtp-news-data"
OBJECT_KEY = "news/latest.json"
ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
TIMEOUT_SECONDS = 20


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def upload_file(path: Path, *, object_key: str = OBJECT_KEY) -> bool:
    # Keep the existing news page key unchanged. Stock feeds use separate objects.
    if object_key not in (OBJECT_KEY, 'stocks/us/instruments.json') and not re.fullmatch(
        r"news/(?:stocks|ai)/us/[A-Z][A-Z0-9.-]{0,14}\.json", object_key
    ):
        raise ValueError("invalid_r2_news_object_key")
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    if not access_key or not secret_key:
        print("[r2-news] credentials_missing", flush=True)
        return False

    body = Path(path).read_bytes()
    payload_hash = hashlib.sha256(body).hexdigest()
    now = dt.datetime.now(dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    encoded_key = "/".join(quote(part, safe="-_.~") for part in object_key.split("/"))
    canonical_uri = f"/{BUCKET}/{encoded_key}"
    host = f"{ACCOUNT_ID}.r2.cloudflarestorage.com"
    canonical_headers = (
        "content-type:application/json\n"
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join((
        "PUT",
        canonical_uri,
        "",
        canonical_headers,
        signed_headers,
        payload_hash,
    ))
    scope = f"{date_stamp}/auto/s3/aws4_request"
    string_to_sign = "\n".join((
        "AWS4-HMAC-SHA256",
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ))
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, "auto")
    k_service = _sign(k_region, "s3")
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(
        k_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    response = requests.put(
        f"{ENDPOINT}{canonical_uri}",
        data=body,
        headers={
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        },
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code // 100 != 2:
        code = ""
        try:
            root = ET.fromstring(response.text)
            code = (root.findtext("Code") or "").strip()
        except Exception:
            code = ""
        print(
            f"[r2-news] upload_failed status={response.status_code} code={code or 'unknown'}",
            flush=True,
        )
        return False
    print(
        f"[r2-news] upload_ok key={object_key} bytes={len(body)}",
        flush=True,
    )
    return True
