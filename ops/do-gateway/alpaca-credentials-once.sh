#!/usr/bin/env bash
# One-time Alpaca Market Data credential input on DigitalOcean console.
# Never print, send, or log key values. No API/trading calls.
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo ALPACA_SETUP_REQUIRES_ROOT >&2; exit 1; }
[[ -c /dev/tty ]] || { echo ALPACA_SETUP_CONSOLE_REQUIRED >&2; exit 1; }
systemctl is-active --quiet gaemigtp-news.service || { echo ALPACA_SETUP_NEWS_WORKER_INACTIVE >&2; exit 1; }
dir=/etc/gaemigtp
target=$dir/alpaca.env
[[ -d "$dir" && ! -L "$dir" && "$(stat -c %U "$dir")" == root ]] || { echo ALPACA_SETUP_CONFIG_DIR_UNSAFE >&2; exit 1; }
[[ ! -e "$target" && ! -L "$target" ]] || { echo ALPACA_SETUP_ALREADY_CONFIGURED >&2; exit 1; }
echo 'Alpaca Market Data API credentials only. Inputs will not be shown.'
KEY=
SECRET=
temp=
cleanup() {
  unset KEY SECRET || true
  if [[ -n "$temp" && -e "$temp" ]]; then rm -f -- "$temp"; fi
}
trap cleanup EXIT
IFS= read -r -s -p 'Alpaca API Key ID: ' KEY </dev/tty || { printf '\n'; echo ALPACA_SETUP_INPUT_FAILED >&2; exit 1; }
printf '\n'
IFS= read -r -s -p 'Alpaca Secret Key: ' SECRET </dev/tty || { printf '\n'; echo ALPACA_SETUP_INPUT_FAILED >&2; exit 1; }
printf '\n'
# Only safe characters representable in a plain systemd EnvironmentFile.
[[ "$KEY" =~ ^[A-Za-z0-9_./+:=@-]{8,256}$ ]] || { echo ALPACA_SETUP_KEY_FORMAT_UNSUPPORTED >&2; exit 1; }
[[ "$SECRET" =~ ^[A-Za-z0-9_./+:=@-]{8,256}$ ]] || { echo ALPACA_SETUP_SECRET_FORMAT_UNSUPPORTED >&2; exit 1; }
temp=$(mktemp "$dir/.alpaca.env.XXXXXXXX")
chmod 0600 "$temp"
chown root:root "$temp"
printf 'APCA_API_KEY_ID=%s\nAPCA_API_SECRET_KEY=%s\n' "$KEY" "$SECRET" > "$temp"
[[ ! -e "$target" && ! -L "$target" ]] || { echo ALPACA_SETUP_CONFIG_APPEARED >&2; exit 1; }
mv -T -- "$temp" "$target"
temp=
unset KEY SECRET
[[ "$(stat -c '%U:%G %a' "$target")" == 'root:root 600' ]] || { echo ALPACA_SETUP_PERMISSIONS_FAILED >&2; exit 1; }
systemctl is-active --quiet gaemigtp-news.service || { echo ALPACA_SETUP_NEWS_WORKER_CHANGED >&2; exit 1; }
echo ALPACA_CREDENTIALS_INSTALLED
echo NO_EXISTING_SERVICES_MODIFIED
