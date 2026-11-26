import json, pathlib, ssl, urllib.request
p = pathlib.Path("/var/lib/gaemigtp-news/us-regular-last-verified.json")
parent = p.parent
lock = pathlib.Path("/var/lib/gaemigtp-news/us-regular-last-verified.lock")
def describe(path):
    try:
        st = path.lstat()
        return "exists=1 type=%s owner_uid=%s owner_gid=%s mode=%04o size=%s" % (
            "symlink" if path.is_symlink() else "file" if path.is_file() else "other",
            st.st_uid, st.st_gid, st.st_mode & 0o777, st.st_size)
    except FileNotFoundError:
        return "exists=0"
print("PARENT " + describe(parent), flush=True)
print("SNAPSHOT " + describe(p), flush=True)
print("LOCK " + describe(lock), flush=True)
if p.is_file() and not p.is_symlink():
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        print("SNAPSHOT_CONTENT day=%s records=%s" % (data.get("day"), len(data.get("items") or {})), flush=True)
    except Exception as exc:
        print("SNAPSHOT_CONTENT_INVALID=" + type(exc).__name__, flush=True)
ctx = ssl._create_unverified_context()
for path in ("/health", "/market/us-industries?include_stocks=1&view=heatmap"):
    with urllib.request.urlopen("https://127.0.0.1" + path, context=ctx, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    if path == "/health":
        print("HTTPS_HEALTH=" + str(data.get("ok")), flush=True)
    else:
        items = data.get("items") or []
        stocks = [x for sector in items for x in (sector.get("stocks") or [])]
        rates = [x for x in stocks if type(x.get("change_pct")) in (int, float)]
        print("INDUSTRY ok=%s sectors=%s stocks=%s percentage_values=%s" %
              (data.get("ok"), len(items), len(stocks), len(rates)), flush=True)
