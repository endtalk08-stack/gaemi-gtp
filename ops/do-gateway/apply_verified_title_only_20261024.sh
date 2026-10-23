#!/usr/bin/env bash
# Headline-only production patch; leave existing article bodies and tags untouched.
set -euo pipefail
cd /opt/gaemigtp-news/app
export PYTHONPATH=/opt/gaemigtp-news/app
venv=/opt/gaemigtp-news/venv/bin/python
test -x "$venv"
test -f ops/.verified-title-helper-next.py
test -f ops/.verified-title-result-next.py
backup="$(mktemp -d ./ops/.title-only-backup.XXXXXX)"
cp -p backend/services/news_result.py "$backup/news_result.py"
cp -p backend/services/news_processed_store.py "$backup/news_processed_store.py"
restore() {
  trap - ERR
  set +e
  install -m 644 "$backup/news_result.py" backend/services/news_result.py
  install -m 644 "$backup/news_processed_store.py" backend/services/news_processed_store.py
  rm -f backend/services/verified_fact_headline.py
  sudo -n /usr/bin/systemctl restart gaemigtp-news.service
  echo TITLE_ONLY_ROLLBACK_DONE
  exit 1
}
trap restore ERR
"$venv" - <<'PY'
from pathlib import Path
import ast
p=Path("backend/services/news_processed_store.py")
s=p.read_text()
old='if market in ("미국", "US") and payload.get("_code_fact_extraction_version") != 2:'
new='if market in ("미국", "US") and (payload.get("_code_fact_extraction_version") != 2 or payload.get("_title_only_revision") != 1):'
if s.count(old)!=1:
    raise RuntimeError("Worker read_signature revision guard differs")
s=s.replace(old,new,1)
ast.parse(s)
p.write_text(s)
print("TITLE_ONLY_REFRESH_GUARD_ADDED",flush=True)
PY
install -m 644 ops/.verified-title-helper-next.py backend/services/verified_fact_headline.py
install -m 644 ops/.verified-title-result-next.py backend/services/news_result.py
"$venv" -m py_compile backend/services/verified_fact_headline.py backend/services/news_result.py backend/services/news_processed_store.py
"$venv" - <<'PY'
from datetime import datetime, timezone
from backend.services.issue_briefs import _article_excerpt
from backend.services.verified_fact_headline import overlay_verified_headlines
now=datetime.now(timezone.utc).isoformat()
body="마이크론은 이익연동 성과급 도입을 발표했다. 성과급은 회사 실적과 연동된다. 새 제도는 2027년부터 시행된다. 네 번째 문장은 제외한다."
summary=_article_excerpt(body)
src={"title":"마이크론, 이익연동 성과급 도입",
     "published_at":now,"url":"https://example.org/story"}
existing={"headline":"기존 제목","summary":summary,
          "tags":["기존핵심키워드"],"stock_names":["마이크론 테크놀로지"]}
out=overlay_verified_headlines([existing],[src],[body],"마이크론 테크놀로지")
assert len(out)==1 and out[0]["headline"]=="마이크론, 이익연동 성과급 도입",out
assert out[0]["summary"]==summary and out[0]["tags"]==existing["tags"]
assert "네 번째" not in out[0]["summary"]
assert out[0]["source_articles"][0]["url"]==src["url"]
print("TITLE_ONLY_VERIFIED_BODY_AND_TAGS_UNTOUCHED",flush=True)
PY
grep -Fq 'PAUSED apply_worker_ai' ops/staged_ai_sequential_batch.py
grep -Fq 'PAUSED process_due_ai_snapshots' ops/staged_auto_ai_daily.py
sudo -n /usr/bin/systemctl restart gaemigtp-news.service
test "$(systemctl is-active gaemigtp-news.service)" = active
trap - ERR
echo TITLE_ONLY_LIVE_PATCH_SUCCESS
