#!/usr/bin/env bash
# Root-owned fixed command permitted to gaemi-deploy WITHOUT arguments.
# Accepts prompt TEXT only; never executes deploy-owned scripts or Python.
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo US_CLOSE_TEST_NEEDS_ROOT; exit 1; }

source_prompt=/home/gaemi-deploy/.gaemi-us-close-reusable/prompt.txt
source_request=/home/gaemi-deploy/.gaemi-us-close-reusable/request.txt
root_runner=/opt/gaemigtp-news/app/backend/us_close_test_runner.py
runtime_dir=/run/gaemi-us-close-test
state_dir=/var/lib/gaemi-us-close-test

[[ -f "$source_prompt" && ! -L "$source_prompt" ]] || { echo TEST_PROMPT_NOT_STAGED; exit 1; }
[[ -f "$source_request" && ! -L "$source_request" ]] || { echo TEST_REQUEST_NOT_STAGED; exit 1; }
[[ -f "$root_runner" && ! -L "$root_runner" ]] || { echo ROOT_RUNNER_MISSING; exit 1; }
[[ "$(stat -c %U "$root_runner")" == root ]] || { echo ROOT_RUNNER_OWNER_INVALID; exit 1; }
[[ "$(systemctl is-active gaemigtp-news.service)" == active ]] || { echo ORIGINAL_WORKER_NOT_ACTIVE; exit 1; }
[[ -r /etc/gaemigtp/news-worker.env ]] || { echo WORKER_ENV_MISSING; exit 1; }

prompt_bytes=$(wc -c < "$source_prompt")
(( prompt_bytes >= 300 && prompt_bytes <= 16000 )) || { echo INVALID_PROMPT_SIZE; exit 1; }
request=$(cat "$source_request")
[[ "$request" =~ ^[a-zA-Z0-9_-]{8,80}$ ]] || { echo INVALID_REQUEST_ID; exit 1; }

exec 9>/run/lock/gaemi-us-close-test.lock
flock -n 9 || { echo US_CLOSE_TEST_ALREADY_RUNNING; exit 1; }
install -d -o root -g root -m 0700 "$state_dir"
ledger="$state_dir/$(date -u +%F).txt"
touch "$ledger"
chmod 0600 "$ledger"
if grep -Fxq "$request" "$ledger"; then
  echo US_CLOSE_TEST_REQUEST_ALREADY_ATTEMPTED
  exit 0
fi
if (( $(wc -l < "$ledger") >= 4 )); then
  echo US_CLOSE_TEST_DAILY_CALL_CAP_REACHED
  exit 1
fi

# Mark BEFORE the paid call so an Actions retry cannot charge a second time.
printf '%s\n' "$request" >> "$ledger"
install -d -o gaemigtp-news -g gaemigtp-news -m 0700 "$runtime_dir"
install -o gaemigtp-news -g gaemigtp-news -m 0600 "$source_prompt" "$runtime_dir/prompt.txt"
trap 'rm -f /run/gaemi-us-close-test/prompt.txt' EXIT

echo "US_CLOSE_TEST_REQUEST=$request"
systemd-run --quiet --wait --pipe --collect \
  -p User=gaemigtp-news \
  -p Group=gaemigtp-news \
  -p WorkingDirectory=/opt/gaemigtp-news/app \
  -p EnvironmentFile=/etc/gaemigtp/news-worker.env \
  -p TimeoutStartSec=140 \
  /opt/gaemigtp-news/venv/bin/python "$root_runner"
[[ "$(systemctl is-active gaemigtp-news.service)" == active ]] || { echo ORIGINAL_WORKER_CHANGED; exit 1; }
echo US_CLOSE_TEST_ONE_CALL_COMPLETE
