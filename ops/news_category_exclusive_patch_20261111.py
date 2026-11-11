"""Patch ONLY category handling into the currently deployed news HTML.

Fetch the live document in CI first so latest styling, layout, and any
deployment-only changes are preserved. Abort if the live format drifts.
"""
from pathlib import Path
import re
import sys

source_file, live_file = map(Path, sys.argv[1:3])
source = source_file.read_text(encoding="utf-8")
live = live_file.read_text(encoding="utf-8")

start = source.index("function category(n){")
end = source.index("const stockSection", start)
category_function = source[start:end].rstrip()

old_category = (
    'const category=n=>n.event_category?.code==="guidance"?"실적 전망":'
    'safeText(n.event_category?.label||n.category||"시장동향");'
)
old_filter = (
    'return category(n)===minor||'
    '(Array.isArray(n.event_matches)&&n.event_matches.some(x=>x?.label===minor));'
)
if live.count(old_category) != 1 or live.count(old_filter) != 1:
    raise SystemExit("LIVE_HTML_LAYOUT_DRIFT: refusing to overwrite changed deployment")
if "function category(n){" in live:
    raise SystemExit("ALREADY_PATCHED: refusing to double-patch")
if not all(term in live for term in (
    "NEWS_R2_URL", "renderNews()", 'data-minor="실적 발표"',
    'data-minor="실적 전망"', 'data-minor="사업 성과"'
)):
    raise SystemExit("NEWS_LAYOUT_GUARD_FAILED")

live = live.replace(old_category, category_function, 1)
live = live.replace(
    old_filter,
    "// Only the primary stock category determines list membership.\n"
    " return category(n)===minor;",
    1,
)
live_file.write_text(live, encoding="utf-8")
print("NEWS_CATEGORY_LIVE_HTML_PATCHED", len(live))
