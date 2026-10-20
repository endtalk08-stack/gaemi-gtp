#!/usr/bin/env bash
# Safely enter Kiwoom REST API credentials directly on the DigitalOcean console.
# Never paste keys into chat, a GitHub commit, an SSH command, or terminal history.
set -Eeuo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo KIWOOM_SETUP_REQUIRES_ROOT >&2; exit 1; }
[[ -c /dev/tty ]] || { echo KIWOOM_SETUP_INTERACTIVE_CONSOLE_REQUIRED >&2; exit 1; }
systemctl is-active --quiet gaemigtp-news.service || {
  echo KIWOOM_SETUP_NEWS_SERVICE_INACTIVE >&2; exit 1;
}
[[ -f /opt/gaemigtp-news/app/backend/providers/kiwoom_us_quotes.py ]] || {
  echo KIWOOM_SETUP_QUOTE_PROVIDER_MISSING >&2; exit 1;
}
dir=/etc/gaemigtp
target=$dir/kiwoom.env
[[ -d "$dir" && ! -L "$dir" && "$(stat -c %U "$dir")" == root ]] || {
  echo KIWOOM_SETUP_CONFIG_DIR_UNSAFE >&2; exit 1;
}
[[ ! -e "$target" && ! -L "$target" ]] || {
  echo KIWOOM_SETUP_ALREADY_CONFIGURED >&2; exit 1;
}
printf '%s\n' 'DigitalOcean: Kiwoom credentials, one-time setup.'
printf '%s\n' 'Enter keys from the Kiwoom portal. Inputs are hidden and will not be printed.'
APP_KEY=
APP_SECRET=
cleanup() {
  unset APP_KEY APP_SECRET || true
  if [[ -n "${temp:-}" && -e "$temp" ]]; then rm -f -- "$temp"; fi
}
trap cleanup EXIT
IFS= read -r -s -p 'Kiwoom APP KEY: ' APP_KEY </dev/tty || { echo; echo KIWOOM_SETUP_INPUT_FAILED >&2; exit 1; }
printf '\n'
IFS= read -r -s -p 'Kiwoom SECRET KEY: ' APP_SECRET </dev/tty || { echo; echo KIWOOM_SETUP_INPUT_FAILED >&2; exit 1; }
printf '\n'
# Avoid quoting/escape hazards in systemd EnvironmentFile; do not echo invalid input.
[[ ${#APP_KEY} -ge 8 && ${#APP_KEY} -le 256 && "$APP_KEY" =~ ^[A-Za-z0-9_./+:=@-]+$ ]] || {
  echo KIWOOM_SETUP_KEY_FORMAT_UNSUPPORTED >&2; exit 1;
}
[[ ${#APP_SECRET} -ge 8 && ${#APP_SECRET} -le 256 && "$APP_SECRET" =~ ^[A-Za-z0-9_./+:=@-]+$ ]] || {
  echo KIWOOM_SETUP_SECRET_FORMAT_UNSUPPORTED >&2; exit 1;
}
temp=$(mktemp "$dir/.kiwoom.env.XXXXXXXX")
chmod 0600 "$temp"
chown root:root "$temp"
printf 'GAEMI_KIWOOM_APP_KEY=%s\nGAEMI_KIWOOM_APP_SECRET=%s\n' "$APP_KEY" "$APP_SECRET" > "$temp"
[[ ! -e "$target" && ! -L "$target" ]] || { echo KIWOOM_SETUP_CONFIG_APPEARED >&2; exit 1; }
mv -T -- "$temp" "$target"
temp=
unset APP_KEY APP_SECRET
[[ "$(stat -c '%U:%G %a' "$target")" == 'root:root 600' ]] || {
  echo KIWOOM_SETUP_PERMISSIONS_FAILED >&2; exit 1;
}
echo KIWOOM_CREDENTIALS_INSTALLED
echo EXISTING_NEWS_SERVICE_UNCHANGED
