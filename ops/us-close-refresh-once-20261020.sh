#!/usr/bin/env bash
# One-time independently scoped US market-close refresh, 2026-10-19 NY session.
# Execute only as root via the fixed /usr/local/sbin path.
set -Eeuo pipefail

[[ $EUID -eq 0 ]] || { echo 'US_CLOSE_ROOT_REQUIRED'; exit 1; }
# Revoke the narrowly scoped temporary sudo grant after this one execution.
trap 'rm -f /etc/sudoers.d/gaemi-us-close-once /usr/local/sbin/gaemi-us-close-refresh-20261020' EXIT

source_file=/home/gaemi-deploy/.gaemi-us-close-20261020/us_market_close.py
target=/opt/gaemigtp-news/app/backend/services/us_market_close.py
backup=/opt/gaemigtp-news/app/backend/services/us_market_close.py.before-selection-20261020
expected_blob=6407e8137f4cde96b491aa47e2544a6a1a7214c9

[[ -f "$source_file" && ! -L "$source_file" ]] || { echo 'US_CLOSE_STAGED_FILE_MISSING'; exit 1; }
[[ -f "$target" && ! -L "$target" ]] || { echo 'US_CLOSE_PRODUCTION_MODULE_MISSING'; exit 1; }
[[ ! -e "$backup" && ! -L "$backup" ]] || { echo 'US_CLOSE_BACKUP_ALREADY_PRESENT'; exit 1; }
[[ "$(git hash-object "$source_file")" == "$expected_blob" ]] || { echo 'US_CLOSE_STAGED_HASH_MISMATCH'; exit 1; }
systemctl is-active --quiet gaemigtp-news.service || { echo 'ORIGINAL_NEWS_WORKER_INACTIVE'; exit 1; }
systemctl cat gaemigtp-us-market-close.service >/dev/null || { echo 'US_CLOSE_SERVICE_ABSENT'; exit 1; }
[[ -r /etc/gaemigtp/news-worker.env ]] || { echo 'US_CLOSE_ENV_MISSING'; exit 1; }
python3 - "$source_file" <<'PY'
import ast, pathlib, sys
ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
PY
python3 - <<'PY'
import pathlib, re, sys
source=pathlib.Path('/etc/gaemigtp/news-worker.env').read_text()
names=set(re.findall(r'(?m)^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=', source))
missing=sorted({'NAVER_CLIENT_ID','NAVER_CLIENT_SECRET','GROQ_API_KEY','NEWS_DATABASE_URL'}-names)
if missing:
    print('US_CLOSE_REQUIRED_KEYS_MISSING: '+','.join(missing))
    sys.exit(1)
print('US_CLOSE_REQUIRED_ENV_KEYS_PRESENT')
PY
cp -p "$target" "$backup"
install -o root -g root -m 0644 "$source_file" "$target"
[[ "$(git hash-object "$target")" == "$expected_blob" ]] || { echo 'US_CLOSE_INSTALLED_HASH_MISMATCH'; exit 1; }
echo 'US_CLOSE_SELECTION_INSTALLED'
# Run one closed US trading session now, despite the current NY day being pre-close.
# systemd loads the existing news worker env without exposing its secret values.
systemd-run --quiet --wait --pipe --collect \
  --unit=gaemi-us-close-one-shot-20261020 \
  -p User=gaemigtp-news -p Group=gaemigtp-news \
  -p WorkingDirectory=/opt/gaemigtp-news/app \
  -p EnvironmentFile=/etc/gaemigtp/news-worker.env \
  -p TimeoutStartSec=140 \
  /opt/gaemigtp-news/venv/bin/python -c 'import datetime,json,sys; from backend.services.us_market_close import publish_once; r=publish_once(now_utc=datetime.datetime(2026,10,20,0,0,tzinfo=datetime.timezone.utc)); print(json.dumps(r,ensure_ascii=False),flush=True); sys.exit(0 if r.get("status")=="published" else 2)'
systemctl is-active --quiet gaemigtp-news.service || { echo 'ORIGINAL_NEWS_WORKER_CHANGED'; exit 1; }
echo 'US_CLOSE_NEW_AI_ANSWER_PUBLISHED'
