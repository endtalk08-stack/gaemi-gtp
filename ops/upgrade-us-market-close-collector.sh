#!/usr/bin/env bash
# Correct only the independent US close article selector installed in PR #32.
# No changes to the existing stock-news worker, systemd units or credentials.
set -Eeuo pipefail
source_file=/home/gaemi-news-check/news-deploy/us-market-close-pr32/us_market_close.py
target=/opt/gaemigtp-news/app/backend/services/us_market_close.py
backup=/opt/gaemigtp-news/app/backend/services/us_market_close.py.before-naver-raw-fix
expected_old=35913f7facfeec32e0be23b3d4d038ac654d4c1b
expected_new=f42cae9e1a728433bf07432f54e0833cc8b15e39
fail() { echo "US_CLOSE_UPGRADE_BLOCKED: $*" >&2; exit 1; }
blob_sha() {
  python3 - "$1" <<'PY'
import hashlib, pathlib, sys
raw=pathlib.Path(sys.argv[1]).read_bytes()
print(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest())
PY
}
[[ $EUID -eq 0 ]] || fail "root required"
[[ -f $source_file && ! -L $source_file ]] || fail "staged reviewed module missing"
[[ -f $target && ! -L $target ]] || fail "current module missing"
systemctl is-active --quiet gaemigtp-news.service || fail "original news worker inactive"
systemctl is-active --quiet gaemigtp-us-market-close.timer || fail "dedicated timer inactive"
[[ $(blob_sha "$source_file") == "$expected_new" ]] || fail "staged blob does not match PR"
current=$(blob_sha "$target")
if [[ $current == "$expected_new" ]]; then
  echo "US_CLOSE_PROVIDER_FIX_ALREADY_INSTALLED"
  exit 0
fi
[[ $current == "$expected_old" ]] || fail "existing module does not match audited initial installation"
[[ ! -e "$backup" && ! -L "$backup" ]] || fail "backup name already exists"
python3 - "$source_file" <<'PY'
import ast,pathlib,sys
ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
PY
temp=$(mktemp /opt/gaemigtp-news/app/backend/services/.us_market_close.XXXXXXXX)
committed=0
rollback() {
  if [[ $committed -eq 0 && -f "$backup" ]]; then
    cp -p "$backup" "$target"
    echo "US_CLOSE_PROVIDER_FIX_ROLLED_BACK"
  fi
  rm -f "$temp"
}
trap rollback EXIT
cp -p "$target" "$backup"
chmod 600 "$backup"
install -o root -g root -m 0644 "$source_file" "$temp"
mv -f "$temp" "$target"
[[ $(blob_sha "$target") == "$expected_new" ]] || fail "final blob mismatch"
systemctl is-active --quiet gaemigtp-news.service || fail "original news worker changed state"
systemctl is-active --quiet gaemigtp-us-market-close.timer || fail "timer changed state"
committed=1
echo "US_CLOSE_PROVIDER_FIX_INSTALLED"
echo "ORIGINAL_NEWS_WORKER_ACTIVE"
echo "NO_PROVIDER_OR_AI_CALL_MADE"
