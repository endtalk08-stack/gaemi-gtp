#!/usr/bin/env bash
# One-time installation of the root-owned, reusable gaemiGTP DigitalOcean gateway.
# The existing news service is not modified, restarted, or disabled.
set -Eeuo pipefail

[[ $EUID -eq 0 ]] || { echo INSTALL_REQUIRES_ROOT >&2; exit 1; }
command -v git >/dev/null
command -v visudo >/dev/null
id gaemi-deploy >/dev/null
id gaemigtp-news >/dev/null

source=/home/gaemi-deploy/.gaemi-gateway/bootstrap/gaemi-do-gateway
target=/usr/local/sbin/gaemi-do-gateway
rulefile=/etc/sudoers.d/gaemi-gateway
expected=dd1f50231f2ab1d36756b6bb24c2aca5b1035c42
rule="gaemi-deploy ALL=(root) NOPASSWD: /usr/local/sbin/gaemi-do-gateway"

[[ -f "$source" && ! -L "$source" ]] || { echo SOURCE_NOT_STAGED >&2; exit 1; }
[[ "$(git hash-object "$source")" == "$expected" ]] || { echo SOURCE_SHA_MISMATCH >&2; exit 1; }
bash -n "$source"
[[ "$(systemctl is-active gaemigtp-news.service)" == active ]] || { echo ORIGINAL_WORKER_NOT_ACTIVE >&2; exit 1; }

if [[ -e "$target" || -L "$target" ]]; then
  [[ -f "$target" && ! -L "$target" && "$(git hash-object "$target")" == "$expected" ]] || {
    echo EXISTING_GATEWAY_DIFFERENT_ABORT >&2; exit 1;
  }
else
  install -o root -g root -m 0750 "$source" "$target"
fi
[[ "$(stat -c %U:%G "$target")" == "root:root" ]] || { echo BAD_GATEWAY_OWNER >&2; exit 1; }

temp=$(mktemp)
trap 'rm -f "$temp"' EXIT
printf '%s\n' "$rule" > "$temp"
chmod 0440 "$temp"
visudo -cf "$temp" >/dev/null
if [[ -e "$rulefile" || -L "$rulefile" ]]; then
  [[ -f "$rulefile" && ! -L "$rulefile" && "$(cat "$rulefile")" == "$rule" ]] || {
    echo EXISTING_SUDOERS_RULE_DIFFERENT_ABORT >&2; exit 1;
  }
else
  install -o root -g root -m 0440 "$temp" "$rulefile"
fi
visudo -cf "$rulefile" >/dev/null
sudo -u gaemi-deploy sudo -n "$target" status >/dev/null
echo GAEMI_GATEWAY_INSTALLED_AND_SSH_USER_VERIFIED
echo ORIGINAL_NEWS_WORKER_UNCHANGED
