#!/usr/bin/env bash
set -euo pipefail
cd /opt/gaemigtp-news/app
export PYTHONPATH=/opt/gaemigtp-news/app
venv=/opt/gaemigtp-news/venv/bin/python
test -x "$venv"
test -f ops/.article-facts-next.py
test -f ops/.news-result-facts-next.py
test -f ops/.deploy-code-facts-next.py
backup="$(mktemp -d ./ops/.code-facts-backup.XXXXXX)"
for f in backend/services/news_result.py backend/services/news_processed_store.py ops/staged_ai_sequential_batch.py ops/staged_auto_ai_daily.py; do
  mkdir -p "$backup/$(dirname "$f")"
  cp -p "$f" "$backup/$f"
done
rollback() {
  trap - ERR
  set +e
  echo CODE_FACTS_ROLLBACK_START
  for f in backend/services/news_result.py backend/services/news_processed_store.py ops/staged_ai_sequential_batch.py ops/staged_auto_ai_daily.py; do
    install -m 644 "$backup/$f" "$f"
  done
  rm -f backend/services/article_fact_keywords.py
  sudo -n /usr/bin/systemctl restart gaemigtp-news.service
  echo CODE_FACTS_ROLLBACK_COMPLETE
  exit 1
}
trap rollback ERR
"$venv" ops/.deploy-code-facts-next.py patch
install -m 644 ops/.article-facts-next.py backend/services/article_fact_keywords.py
install -m 644 ops/.news-result-facts-next.py backend/services/news_result.py
"$venv" -m py_compile backend/services/article_fact_keywords.py backend/services/news_result.py backend/services/news_processed_store.py ops/staged_ai_sequential_batch.py ops/staged_auto_ai_daily.py
"$venv" ops/.deploy-code-facts-next.py verify
sudo -n /usr/bin/systemctl restart gaemigtp-news.service
test "$(systemctl is-active gaemigtp-news.service)" = active
if "$venv" -c 'from backend.services.news_processed_store import database_url; assert database_url()' >/dev/null 2>&1; then
  "$venv" ops/.deploy-code-facts-next.py backfill
else
  echo CODE_FACTS_NEON_BACKFILL_NEEDS_EXTERNAL_DB_CONNECTION
fi
test "$(systemctl is-active gaemigtp-news.service)" = active
trap - ERR
echo CODE_FACTS_DIGITALOCEAN_APPLIED
