#!/usr/bin/env bash
# Unraid read-only daily PES6Web smoke monitor (no installs, git writes or recompiles).
set -euo pipefail
umask 077
ROOT=/mnt/user/appdata/pes6web
WORK=/mnt/user/Downloads/pes6web-work
MON=/mnt/cache/pes6web-monitor
mkdir -p "$MON"
chmod 700 "$MON"
exec 9>"$MON/run.lock"
/usr/bin/flock -n 9 || { echo "Another PES6 monitor is already running."; exit 0; }
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$MON/run-$STAMP.log"
SUMMARY="$MON/latest.txt"
write_summary() {
  local status="$1"
  {
    echo "timestamp=$(date -Is)"
    echo "status=$status"
    echo "git=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unavailable)"
    echo "native_binary=$(stat -c '%s bytes, mtime=%y' "$WORK/psp-web-recomp/build/native-pes6/profiles/web/pspweb_pes6" 2>/dev/null || echo unavailable)"
    if [[ -f "$LOG" ]]; then
      grep -E '^\[pspweb\] (ran |guest stopped:|ge-exit|gl-exit)|^\[frame-check\]' "$LOG" | tail -n 12 || true
      echo "raw_log=$LOG"
    fi
  } > "$SUMMARY.tmp"
  mv -f "$SUMMARY.tmp" "$SUMMARY"
  cat "$SUMMARY"
}
if [[ ! -d "$ROOT" || ! -d "$WORK" ]]; then
  write_summary "skipped: project or private work directory not mounted"
  exit 0
fi
if ! command -v docker >/dev/null || ! docker info >/dev/null 2>&1; then
  write_summary "skipped: Docker unavailable"
  exit 0
fi
# Never compete with an ongoing native/WebAssembly generation or build container.
if [[ -n "$(docker ps -q --filter 'ancestor=pes6web-builder:local')" ]]; then
  write_summary "skipped: another PES6Web builder container is running"
  exit 0
fi
if [[ ! -s "$WORK/psp-web-recomp/build/native-pes6/profiles/web/pspweb_pes6" ]]; then
  write_summary "skipped: native runner missing or empty"
  exit 0
fi
set +e
PES6_WORK_DIR="$WORK" PES6_NATIVE_TIMEOUT=90 \
  /bin/bash "$ROOT/scripts/smoke-native.sh" 300 1 > "$LOG" 2>&1
STATUS=$?
set -e
write_summary "native smoke exit $STATUS (exit 0 alone does NOT mean playable)"
# Only delete old logs created by this monitor, never game inputs or manually run diagnostics.
find "$MON" -maxdepth 1 -type f -name 'run-*.log' -mtime +14 -delete
exit 0
