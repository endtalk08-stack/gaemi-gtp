"""Restore the AI article list (news/ai/us/TOP20.json) after today's interrupted run overwrote it.

Rebuilt from the per-stock files still in R2: Friday's article for every stock not overwritten,
today's article for the 4 that were (NVDA, ANT, TSLA, AAPL; Friday's copy no longer exists).
"""
import datetime as dt, hashlib, hmac, json, os, pathlib, re, sys, urllib.request
from urllib.parse import quote
sys.path.insert(0, "/opt/gaemigtp-news/app")
for line in pathlib.Path("/var/lib/gaemigtp-news/r2.env").read_text().splitlines():
    m = re.match(r"^(?:export\s+)?(R2_[A-Z_]+)\s*=\s*(.*)$", line.strip())
    if m:
        os.environ[m.group(1)] = m.group(2).strip().strip("'\"")
import backend.us_news_ai_daily as job
ACCOUNT, BUCKET = "6cf7450897a598809db421965a07304b", "gaemigtp-news-data"
def sign(key, msg): return hmac.new(key, msg.encode(), hashlib.sha256).digest()
def r2_get(object_key):
    ak, sk = os.environ["R2_ACCESS_KEY_ID"].strip(), os.environ["R2_SECRET_ACCESS_KEY"].strip()
    now = dt.datetime.now(dt.timezone.utc); amz = now.strftime("%Y%m%dT%H%M%SZ"); day = now.strftime("%Y%m%d")
    host = ACCOUNT + ".r2.cloudflarestorage.com"; empty = hashlib.sha256(b"").hexdigest()
    uri = "/" + BUCKET + "/" + "/".join(quote(p, safe="-_.~") for p in object_key.split("/"))
    canon = "\n".join(("GET", uri, "", "host:%s\nx-amz-content-sha256:%s\nx-amz-date:%s\n" % (host, empty, amz),
                       "host;x-amz-content-sha256;x-amz-date", empty))
    scope = day + "/auto/s3/aws4_request"
    k = sign(sign(sign(sign(("AWS4" + sk).encode(), day), "auto"), "s3"), "aws4_request")
    sig = hmac.new(k, "\n".join(("AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(canon.encode()).hexdigest())).encode(), hashlib.sha256).hexdigest()
    req = urllib.request.Request("https://" + host + uri, headers={"Authorization": "AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=host;x-amz-content-sha256;x-amz-date, Signature=%s" % (ak, scope, sig),
                                 "x-amz-content-sha256": empty, "x-amz-date": amz})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        return None if exc.code == 404 else {"error": exc.code}
profiles = job.read_state(job.STATE_PATH).get("profiles") or {}
symbols = sorted(set(profiles) | {s["symbol"] for s in job.read_top20()})
items = []
for sym in symbols:
    data = r2_get("news/ai/us/%s.json" % sym)
    if not data or data.get("error") or data.get("status") != "ok":
        continue
    items.append(data)
    print("FOUND %-5s day=%s generated=%s rank=%s %s" % (sym, data.get("exchange_day"), str(data.get("generated_at"))[:16], data.get("rank"), data.get("headline") or data.get("headline_keyword")), flush=True)
items.sort(key=lambda d: (d.get("rank") or 99))
if len(items) < 5:
    print("TOO_FEW %d, not publishing" % len(items), flush=True); raise SystemExit(1)
job.upload_json({"ok": True, "market": "US", "exchange_day": "2026-11-27",
                 "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "complete": True,
                 "counts": {"ok": len(items)}, "items": items}, "news/ai/us/TOP20.json")
print("RESTORED %d articles" % len(items), flush=True)
