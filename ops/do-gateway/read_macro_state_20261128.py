"""Read-only: show the published macro headlines."""
import json, pathlib
state = json.loads(pathlib.Path("/var/lib/gaemigtp-news/us-macro-news-state.json").read_text(encoding="utf-8"))
for row in state.get("items") or []:
    print("ITEM %s | %s | %s | %s" % (row["published_at"][:16], row["source"], row["title"], row["title_en"]), flush=True)
