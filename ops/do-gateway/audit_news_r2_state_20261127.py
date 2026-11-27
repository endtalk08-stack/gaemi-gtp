"""Read-only: news worker unit settings (flag values only, no secrets) and what R2 holds for news."""
import datetime as dt
import hashlib
import hmac
import json
import os
import pathlib
import subprocess
import sys
from urllib.parse import quote
import xml.etree.ElementTree as ET

sys.path.insert(0, "/opt/gaemigtp-news/app")
import requests
from backend.services import r2_news_uploader as up

FLAGS = ("GAEMIGTP_NEWS_STORAGE", "GAEMIGTP_NEWS_AI_PAUSED", "GAEMIGTP_NEWS_AI_R2_ENABLED", "NEWS_WORKER_INTERVAL_SECONDS")


def load_env(path):
    out = {}
    try:
        for line in pathlib.Path(path).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip().removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    except Exception as exc:
        print("ENV_READ_ERROR %s %s" % (path, type(exc).__name__), flush=True)
    return out


def sign(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def r2_get(path, query=""):
    ak, sk = os.environ["R2_ACCESS_KEY_ID"], os.environ["R2_SECRET_ACCESS_KEY"]
    now = dt.datetime.now(dt.timezone.utc)
    amz, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    empty = hashlib.sha256(b"").hexdigest()
    host = f"{up.ACCOUNT_ID}.r2.cloudflarestorage.com"
    canon_headers = f"host:{host}\nx-amz-content-sha256:{empty}\nx-amz-date:{amz}\n"
    signed = "host;x-amz-content-sha256;x-amz-date"
    canonical = "\n".join(("GET", path, query, canon_headers, signed, empty))
    scope = f"{day}/auto/s3/aws4_request"
    to_sign = "\n".join(("AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(canonical.encode()).hexdigest()))
    k = sign(sign(sign(sign(("AWS4" + sk).encode(), day), "auto"), "s3"), "aws4_request")
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    auth = f"AWS4-HMAC-SHA256 Credential={ak}/{scope}, SignedHeaders={signed}, Signature={sig}"
    return requests.get(up.ENDPOINT + path + ("?" + query if query else ""), timeout=20,
                        headers={"Authorization": auth, "Host": host, "x-amz-content-sha256": empty, "x-amz-date": amz})


def listing(prefix):
    query = "list-type=2&max-keys=200&prefix=" + quote(prefix, safe="")
    resp = r2_get(f"/{up.BUCKET}", query)
    if resp.status_code != 200:
        print("LIST %s HTTP %s" % (prefix, resp.status_code), flush=True)
        return []
    ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
    root = ET.fromstring(resp.content)
    rows = [(c.find("s:Key", ns).text, c.find("s:LastModified", ns).text, int(c.find("s:Size", ns).text))
            for c in root.findall("s:Contents", ns)]
    return rows


def main():
    props = subprocess.run(["systemctl", "show", "gaemigtp-news.service", "-p", "EnvironmentFiles", "-p", "Environment"],
                           text=True, capture_output=True).stdout
    files = [line.split("=", 1)[1].split(" ")[0] for line in props.splitlines() if line.startswith("EnvironmentFiles=")]
    print("UNIT_ENV_FILES " + json.dumps(files), flush=True)
    print("UNIT_ENV_INLINE " + json.dumps([l for l in props.splitlines() if l.startswith("Environment=")]), flush=True)
    merged = {}
    for f in files:
        env = load_env(f)
        print("ENV_FILE %s keys=%s" % (f, ",".join(sorted(env))), flush=True)
        merged.update(env)
    print("FLAGS " + json.dumps({k: merged.get(k) for k in FLAGS}), flush=True)
    r2 = load_env("/var/lib/gaemigtp-news/r2.env")
    os.environ.update({k: v for k, v in r2.items() if k.startswith("R2_")})
    if not os.environ.get("R2_ACCESS_KEY_ID"):
        print("R2_CREDS_UNAVAILABLE", flush=True)
        return
    for prefix in ("news/stocks/us/", "news/ai/us/", "news/latest", "news/us"):
        rows = listing(prefix)
        rows.sort(key=lambda r: r[1], reverse=True)
        print("R2 %s count=%d newest=%s" % (prefix, len(rows), [(k.split('/')[-1], t[:16], s) for k, t, s in rows[:6]]), flush=True)
    for key in ("news/ai/us/NVDA.json", "news/stocks/us/NVDA.json"):
        resp = r2_get(f"/{up.BUCKET}/" + "/".join(quote(p, safe="-_.~") for p in key.split("/")))
        if resp.status_code != 200:
            print("OBJ %s HTTP %s" % (key, resp.status_code), flush=True)
            continue
        data = resp.json()
        summary = {k: (v if not isinstance(v, (list, dict)) else type(v).__name__ + ":" + str(len(v))) for k, v in data.items()}
        print("OBJ %s %s" % (key, json.dumps(summary, ensure_ascii=False)[:600]), flush=True)
        if key.startswith("news/ai/") and data.get("issue_briefs"):
            print("OBJ_AI_SAMPLE " + json.dumps(data["issue_briefs"][0], ensure_ascii=False)[:900], flush=True)


if __name__ == "__main__":
    main()
