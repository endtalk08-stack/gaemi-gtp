#!/usr/bin/env bash
# Temporary stage: restore original AI + article-verification pipeline, no DB deletion.
set -euo pipefail
cd /opt/gaemigtp-news/app
export PYTHONPATH=/opt/gaemigtp-news/app
venv=/opt/gaemigtp-news/venv/bin/python
test -x "$venv"
for f in ops/.restore-orig-news-result.py ops/.restore-orig-news-store.py ops/.restore-orig-ai-sequential.py ops/.restore-orig-ai-daily.py; do
  test -s "$f"
done
backup="$(mktemp -d ./ops/.restore-ai-backup.XXXXXX)"
for f in backend/services/news_result.py backend/services/news_processed_store.py ops/staged_ai_sequential_batch.py ops/staged_auto_ai_daily.py; do
  mkdir -p "$backup/$(dirname "$f")"
  cp -p "$f" "$backup/$f"
done
rollback() {
  trap - ERR
  set +e
  for f in backend/services/news_result.py backend/services/news_processed_store.py ops/staged_ai_sequential_batch.py ops/staged_auto_ai_daily.py; do
    install -m 644 "$backup/$f" "$f"
  done
  sudo -n /usr/bin/systemctl restart gaemigtp-news.service
  echo TEMP_AI_RESTORE_ROLLED_BACK
  exit 1
}
trap rollback ERR
install -m 644 ops/.restore-orig-news-result.py backend/services/news_result.py
install -m 644 ops/.restore-orig-news-store.py backend/services/news_processed_store.py
install -m 644 ops/.restore-orig-ai-sequential.py ops/staged_ai_sequential_batch.py
install -m 644 ops/.restore-orig-ai-daily.py ops/staged_auto_ai_daily.py
"$venv" -m py_compile backend/services/news_result.py backend/services/news_processed_store.py ops/staged_ai_sequential_batch.py ops/staged_auto_ai_daily.py
"$venv" - <<'PY'
import ast
from pathlib import Path
p=Path("ops/staged_ai_sequential_batch.py")
t=p.read_text()
assert 'GAEMIGTP_NEWS_AI_PAUSED' not in t
assert 'def apply_worker_ai(' in t and 'run_stock_batch(' in t
assert 'def apply_unchanged_worker_ai(' in t
s=Path('backend/services/news_result.py').read_text()
assert 'build_issue_briefs(' in s
assert 'body_texts=verified_body_texts' in s
assert 'build_article_fact_briefs(' not in s
assert 'overlay_verified_headlines(' not in s
assert 'def get_shared_stock_news_result(' in s
from backend.services.news_result import get_shared_stock_news_result
print("AI_ORIGINAL_ENTRYPOINT_RESTORED_AND_VERIFIED",flush=True)
PY
sudo -n /usr/bin/systemctl restart gaemigtp-news.service
test "$(systemctl is-active gaemigtp-news.service)" = active
trap - ERR
echo TEMP_AI_NEWS_ORIGINAL_RESTORE_SUCCESS
