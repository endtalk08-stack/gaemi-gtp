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
    props = subprocess.run(["systemctl", "show", "gaemigtp-us-news-ai.service", "-p", "Result", "-p", "ExecMainStatus",
                            "-p", "ExecMainStartTimestamp", "-p", "ExecMainExitTimestamp", "-p", "ActiveState"],
                           text=True, capture_output=True).stdout
    print("SERVICE " + json.dumps(props), flush=True)
    print("TIMER " + subprocess.run(["systemctl", "list-timers", "gaemigtp-us-news-ai.timer", "--all", "--no-pager", "--no-legend"],
                                    text=True, capture_output=True).stdout.strip(), flush=True)
    log = subprocess.run(["journalctl", "-u", "gaemigtp-us-news-ai.service", "--since", "-2h", "--no-pager", "-o", "cat"],
                         text=True, capture_output=True).stdout
    print("JOURNAL_LINES %d" % len(log.splitlines()), flush=True)
    for line in log.splitlines()[-30:]:
        print("J " + line[:200], flush=True)
    try:
        state = json.loads(pathlib.Path("/var/lib/gaemigtp-news/us-news-ai-state.json").read_text())
        print("STATE last_day=%s profiles=%d" % (state.get("last_day"), len(state.get("profiles") or {})), flush=True)
    except Exception as exc:
        print("STATE_ERROR " + type(exc).__name__, flush=True)
    r2 = load_env("/var/lib/gaemigtp-news/r2.env")
    os.environ.update({k: v for k, v in r2.items() if k.startswith("R2_")})
    rows = listing("news/ai/us/")
    print("R2_AI_FILES %d %s" % (len(rows), sorted((k.split("/")[-1], t[:16]) for k, t, s in rows)), flush=True)
    resp = r2_get(f"/{up.BUCKET}/news/ai/us/TOP20.json")
    if resp.status_code != 200:
        print("TOP20 HTTP %s" % resp.status_code, flush=True)
        return
    data = resp.json()
    print("TOP20 day=%s generated=%s counts=%s" % (data.get("exchange_day"), data.get("generated_at"), data.get("counts")), flush=True)
    for item in data.get("items") or []:
        print("ITEM " + json.dumps({k: item.get(k) for k in ("rank", "symbol", "name", "status", "change_pct",
              "headline_keyword", "keywords", "lines", "confidence", "tokens")}, ensure_ascii=False), flush=True)
        for src in (item.get("sources") or [])[:2]:
            print("  SRC " + json.dumps({k: src.get(k) for k in ("source", "title")}, ensure_ascii=False)[:200], flush=True)


if __name__ == "__main__":
    main()
