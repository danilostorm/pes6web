#!/usr/bin/env bash
# Native boot diagnostic for previously built PES6 PSP. Assets and logs stay private.
# Usage: PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work bash scripts/smoke-native.sh [frames] [gl 0|1]
set -euo pipefail
WORK="${PES6_WORK_DIR:-/mnt/user/Downloads/pes6web-work}"
FRAMES="${1:-180}"
GL="${2:-0}"
TIMEOUT="${PES6_NATIVE_TIMEOUT:-120}"
IMAGE="${PES6_BUILDER_IMAGE:-pes6web-builder:local}"
[[ "$FRAMES" =~ ^[1-9][0-9]*$ ]] || { echo "Frames must be positive" >&2; exit 2; }
[[ "$GL" == 0 || "$GL" == 1 ]] || { echo "GL must be 0 or 1" >&2; exit 2; }
[[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]] || { echo "Timeout must be positive (seconds)" >&2; exit 2; }
[[ -d "$WORK" ]] || { echo "Work directory not found: $WORK" >&2; exit 1; }
WORK="$(realpath "$WORK")"
NATIVE="$WORK/psp-web-recomp/build/native-pes6/profiles/web/pspweb_pes6"
ELF="$WORK/psp-web-recomp/games/pes6/root/EBOOT.BIN"
DISC="$WORK/psp-web-recomp/games/pes6/root/disc"
[[ -f "$NATIVE" ]] || { echo "Missing native runner; compile with --native first" >&2; exit 1; }
[[ -s "$ELF" ]] || { echo "Missing decrypted executable: $ELF" >&2; exit 1; }
[[ -d "$DISC/PSP_GAME" ]] || { echo "Missing extracted game files: $DISC" >&2; exit 1; }
command -v docker >/dev/null || { echo "Docker not available" >&2; exit 1; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "Builder Docker image not found: $IMAGE" >&2; exit 1; }
RUN_ID="native-$(date +%Y%m%d-%H%M%S)-$$"
OUTPUT="$WORK/diagnostics/$RUN_ID"
mkdir -p "$OUTPUT"
LOG="$OUTPUT/run.log"
CAPTURE="$OUTPUT/frame.ppm"
echo "PES6 runtime diagnostic: frames=$FRAMES GL=$GL timeout=${TIMEOUT}s"
echo "No rebuilding and no network. Results: $OUTPUT"
set +e
docker run --rm --network none --shm-size=1g \
  --security-opt no-new-privileges:true \
  -e LIBGL_ALWAYS_SOFTWARE=1 \
  -v "$WORK:/work" \
  "$IMAGE" timeout --signal=TERM --kill-after=10s "$TIMEOUT" \
  /work/psp-web-recomp/build/native-pes6/profiles/web/pspweb_pes6 \
  /work/psp-web-recomp/games/pes6/root/EBOOT.BIN \
  --disc /work/psp-web-recomp/games/pes6/root/disc \
  --ms /work/psp-web-recomp/games/pes6/root/ms0 \
  --frames "$FRAMES" --gl "$GL" --threads 0 \
  --dump "/work/diagnostics/$RUN_ID/frame.ppm" 2>&1 | tee "$LOG"
STATUS="${PIPESTATUS[0]}"
set -e
echo "=== PES6 first-boot findings (exit 0 does not mean playable) ==="
grep -E '(\[pspweb\] (ran |guest stopped:|fatal:|wrote )|\[hle\] unimplemented|\[watchdog\]|No recompiled function registered)' "$LOG" | tail -n 45 || true
if [[ -f "$CAPTURE" ]]; then
  echo "Frame capture: $CAPTURE ($(du -h "$CAPTURE" | cut -f1))"
  python3 "$ROOT/tools/check_ppm.py" "$CAPTURE"
else
  echo "No frame captured. Check the log for the first error."
fi
echo "Native test process exit: $STATUS"
echo "To inspect: tail -n 100 '$LOG'"
exit "$STATUS"
