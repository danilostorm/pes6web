#!/usr/bin/env bash
# Persistent Unraid daily cron registration. Preserves other cron jobs.
set -euo pipefail
MARKER=PES6WEB_MONITOR_CRON
GO_MARKER=PES6WEB_MONITOR_AUTOSTART
SCRIPT=/mnt/user/appdata/pes6web/scripts/monitor-native-unraid.sh
MON=/mnt/cache/pes6web-monitor
GO=/boot/config/go
[[ "$(id -u)" -eq 0 && -d /mnt/user/appdata && -f "$GO" ]] || {
  echo "Run as root on Unraid with the array mounted." >&2
  exit 1
}
[[ -s "$SCRIPT" && -x "$SCRIPT" ]] || { echo "Monitor script missing: $SCRIPT" >&2; exit 1; }
command -v crontab >/dev/null || { echo "crontab not installed" >&2; exit 1; }
mkdir -p "$MON"
chmod 700 "$MON"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
(crontab -l 2>/dev/null || true) | grep -v "# $MARKER$" > "$TMP" || true
# 07:40 São Paulo / Unraid local time, before the scheduled ChatGPT 09:00 work cycle.
printf '%s\n' "40 7 * * * /bin/bash $SCRIPT >> $MON/cron.log 2>&1 # $MARKER" >> "$TMP"
crontab "$TMP"
if [[ "$#" -eq 0 || "$1" != "--register-only" ]] && ! grep -Fq "$GO_MARKER" "$GO"; then
  cp -p "$GO" "$GO.backup-pes6web-monitor.$(date +%Y%m%d-%H%M%S)"
  cat >> "$GO" <<'REBOOT'

# PES6WEB_MONITOR_AUTOSTART
(
  until mountpoint -q /mnt/user; do sleep 15; done
  /bin/bash /mnt/user/appdata/pes6web/scripts/install-monitor-cron-unraid.sh --register-only
) >/dev/null 2>&1 &
REBOOT
fi
echo "PES6Web cron registered: daily 07:40 (local Unraid time)."
echo "Status: crontab -l | grep $MARKER"
echo "Results: cat $MON/latest.txt"
echo "This cron only runs a bounded native smoke test; it never changes source code."
