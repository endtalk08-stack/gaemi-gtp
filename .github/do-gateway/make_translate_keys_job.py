"""Write the one-time gateway job that installs the translation keys on the server.

Keys come from the GitHub environment secrets DEEPL_API_KEY / GOOGLE_TRANSLATE_API_KEY
(either may be missing). The job writes /var/lib/gaemigtp-news/translate.env (0600,
service user only) and checks each key without printing it.
"""
import json
import os
import re
import sys

keys = {}
deepl = os.environ.get("DEEPL_API_KEY", "").strip()
google = os.environ.get("GOOGLE_TRANSLATE_API_KEY", "").strip()
if deepl:
    if not re.fullmatch(r"[A-Za-z0-9-]{20,80}(:fx)?", deepl):
        raise SystemExit("DEEPL_API_KEY has an unexpected format")
    keys["DEEPL_API_KEY"] = deepl
if google:
    if not re.fullmatch(r"[A-Za-z0-9_-]{30,60}", google):
        raise SystemExit("GOOGLE_TRANSLATE_API_KEY has an unexpected format")
    keys["GOOGLE_TRANSLATE_API_KEY"] = google
if not keys:
    raise SystemExit("no translation key secret is set")
print("TRANSLATE_KEYS_PRESENT " + " ".join(sorted(keys)))

JOB = r'''
import json, os, tempfile, urllib.error, urllib.parse, urllib.request
KEYS = json.loads(%s)
target = "/var/lib/gaemigtp-news/translate.env"
fd, tmp = tempfile.mkstemp(dir="/var/lib/gaemigtp-news", prefix=".translate-")
with os.fdopen(fd, "w") as f:
    for name, value in KEYS.items():
        f.write(name + "=" + value + "\n")
os.chmod(tmp, 0o600)
os.replace(tmp, target)
print("TRANSLATE_ENV_WRITTEN " + " ".join(sorted(KEYS)), flush=True)

def call(request):
    try:
        with urllib.request.urlopen(request, timeout=20) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception as exc:
        return type(exc).__name__, None

if "DEEPL_API_KEY" in KEYS:
    key = KEYS["DEEPL_API_KEY"]
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    status, data = call(urllib.request.Request("https://%%s/v2/usage" %% host,
        headers={"Authorization": "DeepL-Auth-Key " + key, "User-Agent": "gaemiGTP-news/1.0"}))
    used = (data or {}).get("character_count"); limit = (data or {}).get("character_limit")
    print("DEEPL_CHECK status=%%s used=%%s limit=%%s" %% (status, used, limit), flush=True)
if "GOOGLE_TRANSLATE_API_KEY" in KEYS:
    body = json.dumps({"q": ["Federal Reserve"], "source": "en", "target": "ko", "format": "text"}).encode()
    status, data = call(urllib.request.Request("https://translation.googleapis.com/language/translate/v2",
        data=body, method="POST", headers={"X-Goog-Api-Key": KEYS["GOOGLE_TRANSLATE_API_KEY"],
        "Content-Type": "application/json", "User-Agent": "gaemiGTP-news/1.0"}))
    sample = ((data or {}).get("data") or {}).get("translations") or [{}]
    print("GOOGLE_CHECK status=%%s sample=%%s" %% (status, sample[0].get("translatedText")), flush=True)
''' % repr(json.dumps(keys))

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(JOB)
