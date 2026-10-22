"""Read-only production verification for US Naver news and US-close service."""
import json, subprocess
from backend.providers import naver_news
print("NAVER_CONFIGURED",naver_news.is_configured(),flush=True)
if naver_news.is_configured():
    try:
        rows=naver_news.search_news("엔비디아",display=1,raise_on_error=True)
        print("NAVER_NEWS_TEST",json.dumps([{"title":r.get("title"),"originallink":r.get("originallink"),"pubDate":r.get("pubDate")} for r in rows],ensure_ascii=False),flush=True)
    except Exception as ex:
        print("NAVER_NEWS_ERROR",type(ex).__name__,str(ex)[:200],flush=True)
for unit in ("gaemigtp-us-market-close.timer","gaemigtp-us-market-close.service"):
    for verb in ("is-active","is-enabled"):
        r=subprocess.run(["systemctl",verb,unit],capture_output=True,text=True,timeout=5)
        print("SYSTEMD",unit,verb,r.returncode,r.stdout.strip(),r.stderr.strip()[:100],flush=True)
