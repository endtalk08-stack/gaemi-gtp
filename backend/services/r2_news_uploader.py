"""Upload stock-news and market-data JSON to Cloudflare R2 using S3 SigV4.

No third-party AWS SDK is required. Credentials are read from environment only.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import math
import os
import re
from pathlib import Path
from urllib.parse import quote

import requests
import xml.etree.ElementTree as ET

ACCOUNT_ID = "6cf7450897a598809db421965a07304b"
BUCKET = "gaemigtp-news-data"
ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
TIMEOUT_SECONDS = 20


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()



def read_recovered_news_snapshot(*, object_key: str = "news/recovered/20261109.json"):
    """Read the user-approved historical R2 backup without news API calls.

    Fixed path only: this function never accesses arbitrary remote URLs/objects.
    Fail closed when credentials, signature or saved JSON is invalid.
    """
    approved_snapshots = {
        "news/recovered/20261109.json": 24,
        "news/archive/20261112/ddc51420ed55217c2088705ff0a3a3397ba98a4ebc3e5749850bb421ecaf224f.json": 106,
    }
    if object_key not in approved_snapshots:
        raise ValueError("invalid_recovery_key")
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    if not access_key or not secret_key:
        raise RuntimeError("recovery_r2_credentials_missing")
    now = dt.datetime.now(dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    day = now.strftime("%Y%m%d")
    empty_hash = hashlib.sha256(b"").hexdigest()
    host = f"{ACCOUNT_ID}.r2.cloudflarestorage.com"
    uri = f"/{BUCKET}/" + "/".join(quote(part, safe="-_.~") for part in object_key.split("/"))
    headers_canonical = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{empty_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical = "\n".join(("GET", uri, "", headers_canonical, signed_headers, empty_hash))
    scope = f"{day}/auto/s3/aws4_request"
    to_sign = "\n".join((
        "AWS4-HMAC-SHA256", amz_date, scope,
        hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    ))
    key = _sign((("AWS4" + secret_key).encode("utf-8")), day)
    key = _sign(key, "auto")
    key = _sign(key, "s3")
    key = _sign(key, "aws4_request")
    signature = hmac.new(key, to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    auth = (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    response = requests.get(
        ENDPOINT + uri,
        headers={
            "Authorization": auth,
            "Host": host,
            "x-amz-content-sha256": empty_hash,
            "x-amz-date": amz_date,
        },
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise RuntimeError("r2_recovery_read_failed_status_" + str(response.status_code))
    if len(response.content) > 1_500_000:
        raise ValueError("recovery_snapshot_too_large")
    data = response.json()
    if (not isinstance(data, dict) or data.get("ok") is not True
            or not isinstance(data.get("items"), list)
            or len(data["items"]) != approved_snapshots[object_key]):
        raise ValueError("invalid_recovery_snapshot")
    return data



def read_r2_json(object_key: str, *, max_bytes: int = 1_500_000):
    """Read only allow-listed chart and instrument JSON from R2."""
    if (object_key != "stocks/us/instruments.json"
            and not re.fullmatch(r"charts/us/[A-Z][A-Z0-9.-]{0,14}/daily\\.json", object_key)):
        raise ValueError("invalid_r2_read_key")
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    if not access_key or not secret_key:
        raise RuntimeError("r2_read_credentials_missing")
    now = dt.datetime.now(dt.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    day = now.strftime("%Y%m%d")
    empty_hash = hashlib.sha256(b"").hexdigest()
    host = f"{ACCOUNT_ID}.r2.cloudflarestorage.com"
    uri = f"/{BUCKET}/" + "/".join(quote(part, safe="-_.~") for part in object_key.split("/"))
    canonical_headers = f"host:{host}\\n" f"x-amz-content-sha256:{empty_hash}\\n" f"x-amz-date:{amz_date}\\n"
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical = "\\n".join(("GET", uri, "", canonical_headers, signed_headers, empty_hash))
    scope = f"{day}/auto/s3/aws4_request"
    to_sign = "\\n".join(("AWS4-HMAC-SHA256", amz_date, scope,
                            hashlib.sha256(canonical.encode("utf-8")).hexdigest()))
    key = _sign(("AWS4" + secret_key).encode("utf-8"), day)
    key = _sign(key, "auto")
    key = _sign(key, "s3")
    key = _sign(key, "aws4_request")
    signature = hmac.new(key, to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = ("AWS4-HMAC-SHA256 "
                     f"Credential={access_key}/{scope}, "
                     f"SignedHeaders={signed_headers}, Signature={signature}")
    response = requests.get(
        ENDPOINT + uri,
        headers={"Authorization": authorization, "Host": host,
                 "x-amz-content-sha256": empty_hash, "x-amz-date": amz_date},
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise RuntimeError("r2_read_failed_status_" + str(response.status_code))
    if len(response.content) > max_bytes:
        raise ValueError("r2_object_too_large")
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("invalid_r2_json_object")
    return data



def read_daily_chart(symbol: str):
    """Read one allow-listed daily chart from R2; no database fallback."""
    symbol = str(symbol or "").strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", symbol):
        raise ValueError("invalid_chart_symbol")
    data = read_r2_json(f"charts/us/{symbol}/daily.json")
    if data is None:
        return None
    candles = data.get("candles")
    if (data.get("schema_version") != 1 or data.get("market") != "US"
            or data.get("symbol") != symbol or data.get("interval") != "daily"
            or not isinstance(candles, list) or not candles
            or data.get("count") != len(candles)):
        raise ValueError("invalid_r2_daily_chart")
    previous = ""
    for row in candles:
        if not isinstance(row, dict) or not re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", str(row.get("date") or "")):
            raise ValueError("invalid_r2_daily_candle")
        if row["date"] <= previous:
            raise ValueError("invalid_r2_daily_order")
        previous = row["date"]
        prices = [row.get(k) for k in ("open", "high", "low", "close")]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in prices):
            raise ValueError("invalid_r2_daily_price")
        o, h, l, c = prices
        if l > min(o, c) or max(o, c) > h:
            raise ValueError("invalid_r2_daily_ohlc")
        volume = row.get("volume")
        if volume is not None and (type(volume) is not int or volume < 0):
            raise ValueError("invalid_r2_daily_volume")
    return data



def upload_file(path: Path, *, object_key: str) -> bool:
    # Unified news-page snapshots are retired; publish only scoped stock/news objects.
    if object_key != 'stocks/us/instruments.json' and not re.fullmatch(
        r"(?:news/macro/us/feed|news/(?:stocks|ai)/us/[A-Z][A-Z0-9.-]{0,14}|charts/us/[A-Z][A-Z0-9.-]{0,14}/daily|news/archive/[0-9]{8}/[0-9a-f]{64})\.json", object_key
    ):
        raise ValueError("invalid_r2_news_object_key")
    access_key = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    if not access_key or not secret_key:
        print("[r2-news] credentials_missing", flush=True)
        return False

    body = Path(path).read_bytes()
    payload_hash = hashlib.sha256(body).hexdigest()
    # Archive writes are content-addressed and must never overwrite history.
    archive = object_key.startswith("news/archive/")
    if archive and object_key.rsplit("/", 1)[-1] != payload_hash + ".json":
        raise ValueError("archive_content_hash_mismatch")
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
    if archive:
        canonical_headers = canonical_headers.replace(
            f"host:{host}\n", f"host:{host}\nif-none-match:*\n"
        )
    signed_headers = ("content-type;host;"
                      + ("if-none-match;" if archive else "")
                      + "x-amz-content-sha256;x-amz-date")
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
            **({"If-None-Match": "*"} if archive else {}),
        },
        timeout=TIMEOUT_SECONDS,
    )
    if archive and response.status_code == 412:
        # Existing immutable copy: do not replace it on a worker restart.
        print(f"[r2-news] archive_exists key={object_key}", flush=True)
        return True
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
