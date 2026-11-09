"""Read-only verification of news-page source installed on DigitalOcean."""
import hashlib
from pathlib import Path
import subprocess

path = Path("/opt/gaemigtp-news/app/backend/services/tradingview_news_page.py")
if not path.is_file() or path.is_symlink():
    print("NEWS_PAGE_FILE_PRESENT=0", flush=True)
    raise SystemExit(2)
source = path.read_text(encoding="utf-8")
print("NEWS_PAGE_FILE_PRESENT=1", flush=True)
print("NEWS_PAGE_SHA256=" + hashlib.sha256(source.encode("utf-8")).hexdigest(), flush=True)
print("NEWS_PAGE_NEW_BODY_NORMALIZER=" + str("def _article_body(value):" in source), flush=True)
print("NEWS_PAGE_NEW_BODY_WIRING=" + str('body = _article_body(article.get("detail_body"))' in source), flush=True)
print("NEWS_PAGE_REUTERS_FILTER=" + str("로이터는 영어 원어민이 아닌 독자들의 편의를 위해" in source), flush=True)
for unit in ("gaemigtp-news.service", "gaemigtp-tradingview-news.service"):
    proc = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True, timeout=8)
    print("NEWS_UNIT_" + unit + "=" + proc.stdout.strip(), flush=True)
print("NEWS_PAGE_READONLY_VERIFY_COMPLETE=1", flush=True)
