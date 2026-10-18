#!/usr/bin/env bash
# Install only the independent US-market-close job. No stock worker restart.
# Run from a verified root console once, after the staging GitHub Action succeeds.
set -Eeuo pipefail

stage=/home/gaemi-news-check/news-deploy/us-market-close-pr32
app=/opt/gaemigtp-news/app
systemd=/etc/systemd/system
timer=gaemigtp-us-market-close.timer
release_py="$stage/us_market_close.py"
job_py="$stage/us_market_close_job.py"
service_unit="$stage/gaemigtp-us-market-close.service"
timer_unit="$stage/gaemigtp-us-market-close.timer"

fail() { echo "US_CLOSE_INSTALL_BLOCKED: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail "root login required"
[[ -d $stage && ! -L $stage ]] || fail "verified staging folder missing"
[[ -d $app/backend/services && -d $app/backend ]] || fail "existing news app paths missing"
[[ -x /opt/gaemigtp-news/venv/bin/python ]] || fail "existing python venv missing"
id gaemigtp-news >/dev/null || fail "existing service account missing"
systemctl is-active --quiet gaemigtp-news.service || fail "existing news worker is not active"
[[ -r /etc/gaemigtp/news-worker.env ]] || fail "existing worker env file missing"

# Refuse to overwrite any existing application code or systemd units.
for target in \
  "$app/backend/services/us_market_close.py" \
  "$app/backend/us_market_close_job.py" \
  "$systemd/gaemigtp-us-market-close.service" \
  "$systemd/$timer"; do
  [[ ! -e "$target" && ! -L "$target" ]] || fail "target already exists; refusing overwrite: $target"
done

# These are the exact GitHub *blob* SHAs verified from PR #32.
verify_blob() {
  local source=$1 expected=$2 actual
  [[ -f "$source" && ! -L "$source" ]] || fail "staged file missing: $source"
  actual=$(python3 - "$source" <<'PY'
import hashlib, sys
with open(sys.argv[1], 'rb') as handle:
    payload = handle.read()
print(hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest())
PY
)
  [[ $actual == "$expected" ]] || fail "staged file does not match reviewed PR: $source"
}
verify_blob "$release_py"    35913f7facfeec32e0be23b3d4d038ac654d4c1b
verify_blob "$job_py"        e75ce97a0ccbfac125b39c81078a227100dc222f
verify_blob "$service_unit"  953afcb6d1ba781f76601e8b5ab85df6f8f45556
verify_blob "$timer_unit"    6352e697fbea501694bb83033dc6a6158662409c

# Parse only key names, never print secrets.
python3 - <<'PY' || fail "service environment missing required API/DB credentials"
import pathlib, re, sys
p = pathlib.Path('/etc/gaemigtp/news-worker.env')
text = p.read_text(encoding='utf-8')
names = set(re.findall(r'(?m)^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=', text))
needed = {'NAVER_CLIENT_ID', 'NAVER_CLIENT_SECRET', 'GROQ_API_KEY', 'NEWS_DATABASE_URL'}
missing = sorted(needed - names)
if missing:
    print("US_CLOSE_ENV_KEYS_MISSING: " + ", ".join(missing))
    sys.exit(1)
print("US_CLOSE_ENV_KEYS_PRESENT")
PY

# Parse only; do not call API or start the new AI job now.
python3 - "$release_py" "$job_py" <<'PY' || fail "Python syntax invalid"
import ast, pathlib, sys
for path in sys.argv[1:]:
    ast.parse(pathlib.Path(path).read_text(encoding='utf-8'))
print("US_CLOSE_CODE_PARSED")
PY
systemd-analyze verify "$service_unit" "$timer_unit" >/dev/null || fail "systemd unit invalid"

committed=0
rollback_if_failed() {
  if [[ $committed -eq 0 ]]; then
    systemctl disable --now "$timer" >/dev/null 2>&1 || true
    rm -f "$app/backend/services/us_market_close.py" \
          "$app/backend/us_market_close_job.py" \
          "$systemd/gaemigtp-us-market-close.service" \
          "$systemd/$timer"
    systemctl daemon-reload >/dev/null 2>&1 || true
    echo "US_CLOSE_INSTALL_ROLLED_BACK"
  fi
}
trap rollback_if_failed EXIT

install -o root -g root -m 0644 "$release_py" "$app/backend/services/us_market_close.py"
install -o root -g root -m 0644 "$job_py" "$app/backend/us_market_close_job.py"
install -o root -g root -m 0644 "$service_unit" "$systemd/gaemigtp-us-market-close.service"
install -o root -g root -m 0644 "$timer_unit" "$systemd/$timer"
systemctl daemon-reload
systemctl enable --now "$timer" >/dev/null
systemctl is-active --quiet "$timer" || fail "new timer not active"
systemctl is-active --quiet gaemigtp-news.service || fail "original news worker changed state"
committed=1
echo "US_CLOSE_TIMER_INSTALLED"
systemctl list-timers --all --no-pager "$timer"
echo "ORIGINAL_NEWS_WORKER_ACTIVE"
echo "NO_AI_CALL_MADE_BY_INSTALLER"
