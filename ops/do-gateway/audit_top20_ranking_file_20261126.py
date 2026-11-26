import json, pathlib, datetime
p=pathlib.Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
print("RANKING_FILE_EXISTS=" + str(p.is_file()), flush=True)
if p.is_file() and not p.is_symlink():
    st=p.stat()
    print("RANKING_FILE_MTIME_UTC="+datetime.datetime.fromtimestamp(st.st_mtime,datetime.timezone.utc).isoformat(), flush=True)
    data=json.loads(p.read_text(encoding="utf-8"))
    print("CAPTURED_AT="+str(data.get("captured_at")), flush=True)
    rows=data.get("items") or []
    valid=[r for r in rows if type(r.get("change_pct")) in (int,float)]
    print("ROWS=%d NUMERIC_CHANGE=%d" % (len(rows),len(valid)), flush=True)
    for row in rows[:10]:
        print("ROW=%s|price=%s|change_pct=%s|exchange=%s|captured_at=%s" %
              (row.get("symbol"),row.get("price"),row.get("change_pct"),row.get("exchange"),row.get("captured_at")), flush=True)
