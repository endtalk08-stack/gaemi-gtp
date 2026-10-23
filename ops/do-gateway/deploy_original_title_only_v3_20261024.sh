#!/usr/bin/env bash
set -euo pipefail
cd /opt/gaemigtp-news/app
export PYTHONPATH=/opt/gaemigtp-news/app:/opt/gaemigtp-news/app/ops
venv=/opt/gaemigtp-news/venv/bin/python
test -x "$venv"
backup="$(mktemp -d ./ops/.verified-title-v3-backup.XXXXXX)"
paths=(backend/services/news_result.py backend/services/verified_fact_headline.py backend/services/news_processed_store.py ops/staged_ai_sequential_batch.py ops/staged_auto_ai_daily.py ops/staged_ai_issue_store.py)
for target in "${paths[@]}"; do mkdir -p "$backup/$(dirname "$target")"; cp -p "$target" "$backup/$target"; done
rollback() {
  trap - ERR
  set +e
  for target in "${paths[@]}"; do install -m 644 "$backup/$target" "$target"; done
  sudo -n /usr/bin/systemctl restart gaemigtp-news.service
  echo TITLE_V3_ROLLED_BACK
  exit 1
}
trap rollback ERR
install -m 644 ops/.final-news-result.py backend/services/news_result.py
install -m 644 ops/.final-title-helper.py backend/services/verified_fact_headline.py
install -m 644 ops/.final-news-store.py backend/services/news_processed_store.py
install -m 644 ops/.final-ai-paused.py ops/staged_ai_sequential_batch.py
install -m 644 ops/.final-ai-daily-paused.py ops/staged_auto_ai_daily.py
install -m 644 ops/.final-ai-issue-store.py ops/staged_ai_issue_store.py
"$venv" -m py_compile backend/services/news_result.py backend/services/verified_fact_headline.py backend/services/news_processed_store.py ops/staged_ai_sequential_batch.py ops/staged_auto_ai_daily.py ops/staged_ai_issue_store.py
"$venv" - <<'PY'
from pathlib import Path
import os
from datetime import datetime,timezone
news=Path('backend/services/news_result.py').read_text()
assert news.count('body_texts=verified_body_texts')==1
assert news.count('overlay_verified_headlines(')==1
assert 'build_article_fact_briefs(' not in news
assert '_title_only_revision": 3' in news
assert 'payload.get("_title_only_revision") != 3' in Path('backend/services/news_processed_store.py').read_text()
from backend.services.issue_briefs import _article_excerpt
from backend.services.verified_fact_headline import overlay_verified_headlines
body="마이크론은 제도를 발표했다. 성과급은 내년부터 도입된다. 직원에게 지급된다. 네 번째 문장이다."
excerpt=_article_excerpt(body)
src={'title':'마이크론, 이익연동 성과급 도입','url':'https://example.org/a','published_at':datetime.now(timezone.utc).isoformat()}
original={'headline':'기존 제목','summary':excerpt,'tags':['기존키워드'],'stock_names':['마이크론 테크놀로지']}
v=overlay_verified_headlines([original],[src],[body],'마이크론 테크놀로지')
assert len(v)==1 and v[0]['summary']==excerpt and v[0]['tags']==original['tags']
assert v[0]['headline']=='마이크론, 이익연동 성과급 도입' and v[0]['source_articles'][0]['url']==src['url']
assert os.environ.get('GAEMIGTP_NEWS_AI_PAUSED','1') != '0'
from staged_ai_sequential_batch import apply_worker_ai, apply_unchanged_worker_ai
from staged_auto_ai_daily import process_due_ai_snapshots
assert apply_worker_ai(store=None,market='미국',stock_name='마이크론 테크놀로지',raw=[],fingerprint='',result={},params={}) is None
assert apply_unchanged_worker_ai(store=None,market='미국',stock_name='마이크론 테크놀로지',raw=[],fingerprint='',params={}) is None
assert process_due_ai_snapshots()==0
print('TITLE_V3_ARTICLE_3_SENTENCES_TAGS_AI_PAUSE_VERIFIED',flush=True)
PY
sudo -n /usr/bin/systemctl restart gaemigtp-news.service
test "$(systemctl is-active gaemigtp-news.service)" = active
trap - ERR
echo TITLE_V3_LIVE_ACTIVATED_AI_PAUSED
