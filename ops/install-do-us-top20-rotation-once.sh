#!/usr/bin/env bash
# Explicit root-only installation of the previously STAGED, reviewed patch.
# Never invoke until administrator has inspected the live selector and approved
# one worker restart. No other service, DB schema, or generated news is changed.
set -Eeuo pipefail
stage=/home/gaemi-news-check/news-deploy/us-top20-rotation-pr131
target=/opt/gaemigtp-news/app/backend
svc=gaemigtp-news.service
backup="/opt/gaemigtp-news/backups/us-top20-rotation-$(date -u +%Y%m%dT%H%M%SZ)"
fail(){ echo "NEWS_ROTATION_INSTALL_BLOCKED: $*" >&2; exit 1; }
[[ "$EUID" -eq 0 ]] || fail "root administrator required"
[[ -d "$stage" && ! -L "$stage" ]] || fail "staged review folder missing"
systemctl is-active --quiet "$svc" || fail "existing service inactive"
[[ ! -e "$target/services/us_top20_rotation.py" ]] || fail "rotation module unexpectedly already installed"

# Match *exactly* the live source that was inspected before producing this patch.
[[ "$(sha256sum "$target/news_worker.py" | cut -d' ' -f1)" = d274422a687d89af56868a956dc77317945220cebac13b620f20c78f5ef73967 ]] || fail "live worker changed since review"
[[ "$(sha256sum "$target/services/news_result.py" | cut -d' ' -f1)" = 0f79aeb99a5931f22273ce4250c8cc3c9eca08734811add49c5ffd7a798f7a58 ]] || fail "live news result changed since review"

for pair in news_worker.py:b1706dd0ab3200d7c3f3fbce4c086ef2266cf66e834a29aa936e2f640b85c2cd news_result.py:66a309ea15d0079e0f3603c6f44670abf1d5fe82c67e0e4635a50936e24ce681 us_top20_rotation.py:53b7082d2bd009867377b70c813b7bc1f1f773939a7d3c3f474859f6f6a65b65; do
  file="${pair%%:*}" expected="${pair#*:}"
  [[ -f "$stage/$file" && ! -L "$stage/$file" ]] || fail "missing reviewed staged file $file"
  [[ "$(sha256sum "$stage/$file" | cut -d' ' -f1)" == "$expected" ]] || fail "staged checksum changed $file"
done
/opt/gaemigtp-news/venv/bin/python -m py_compile "$stage/news_worker.py" "$stage/news_result.py" "$stage/us_top20_rotation.py" || fail "syntax"
[[ ! -e "$backup" ]] || fail "backup name conflict"
install -d -m 700 "$backup"
cp -p "$target/news_worker.py" "$backup/news_worker.py"
cp -p "$target/services/news_result.py" "$backup/news_result.py"
rolled_back=0
rollback() {
  if [[ "$rolled_back" -eq 1 ]]; then
    cp -p "$backup/news_worker.py" "$target/news_worker.py"
    cp -p "$backup/news_result.py" "$target/services/news_result.py"
    rm -f "$target/services/us_top20_rotation.py"
    systemctl restart "$svc" || true
    echo NEWS_ROTATION_INSTALL_ROLLED_BACK
  fi
}
trap rollback EXIT
rolled_back=1

install -o root -g root -m 644 "$stage/news_worker.py" "$target/news_worker.py"
# Preserve the current news_result owner for the existing deployment workflow.
source_owner=$(stat -c '%u' "$backup/news_result.py")
source_group=$(stat -c '%g' "$backup/news_result.py")
install -o "$source_owner" -g "$source_group" -m 644 "$stage/news_result.py" "$target/services/news_result.py"
install -o root -g root -m 644 "$stage/us_top20_rotation.py" "$target/services/us_top20_rotation.py"
systemctl restart "$svc" || fail "service restart failure"
systemctl is-active --quiet "$svc" || fail "service inactive after restart"
# Runtime import check without starting a second worker.
(cd /opt/gaemigtp-news/app && /opt/gaemigtp-news/venv/bin/python -c 'from backend.services.us_top20_rotation import plan_tick, finish_tick; print("ROTATION_IMPORT_OK")') || fail "import"
rolled_back=0
echo "NEWS_ROTATION_INSTALL_COMPLETE"
echo "BACKUP_PATH=$backup"
systemctl show "$svc" -p ActiveState -p SubState -p MainPID
