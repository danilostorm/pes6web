#!/usr/bin/env bash
# Bounded, private native boot-recovery loop: only handles validated missing entries.
# Run after an initial --native build. No network, ISO modifications or public assets.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${PES6_WORK_DIR:-/mnt/user/Downloads/pes6web-work}"
[[ -d "$WORK/psp-web-recomp" ]] || { echo "Missing existing recompilation work tree" >&2; exit 1; }
WORK="$(realpath "$WORK")"
N="${1:-4}"
[[ "$N" =~ ^[1-9][0-9]*$ ]] && (( N <= 8 )) || { echo "Recovery iterations must be 1 to 8" >&2; exit 2; }
docker image inspect pes6web-builder:local >/dev/null 2>&1 || { echo "Missing builder image" >&2; exit 1; }
ELF="$WORK/psp-web-recomp/games/pes6/root/EBOOT.BIN"
SEEDS="$WORK/diagnostics/verified-extra-seeds.txt"
[[ -s "$ELF" && -s "$SEEDS" ]] || { echo "Missing decrypted game or private seed list" >&2; exit 1; }
for ((iteration=1; iteration<=N; iteration++)); do
  echo "=== Native attempt $iteration/$N ==="
  PES6_WORK_DIR="$WORK" PES6_NATIVE_TIMEOUT="${PES6_NATIVE_TIMEOUT:-90}" \
    bash "$ROOT/scripts/smoke-native.sh" 180 0
  LOG="$(ls -1t "$WORK"/diagnostics/native-*/run.log | head -n 1)"
  if grep -qE '\[pspweb\] ran 180 frames' "$LOG"; then
    echo "Completed target frame count. Inspect framebuffer and gameplay before declaring success."
    exit 0
  fi
  if ! python3 "$ROOT/tools/recover_native_entry.py" --log "$LOG" --elf "$ELF" --seeds "$SEEDS"; then
    echo "No safe automatic entry recovery. Inspect $LOG."
    exit 1
  fi
  ENTRIES="$(tr -d '\r\n' < "$SEEDS")"
  echo "Rebuilding native with $(awk -F, '{print NF}' <<< "$ENTRIES") private entry points"
  docker run --rm -i --network none --shm-size=2g \
    -v "$WORK:/project/work" -w /project/work/psp-web-recomp \
    -e JOBS=2 -e "PSPRECOMP_EXTRA_SEEDS=$ENTRIES" \
    -e "PSPRECOMP_FALLTHROUGH_RANGES=${PES6_FALLTHROUGH_RANGES:-0x08984000-0x08987000,0x08860000-0x08870000,0x088B0000-0x088C0000,0x088C0000-0x088C5000}" \
    pes6web-builder:local timeout --kill-after=15s 900s \
    bash -lc 'bash scripts/generate.sh pes6 games/pes6/root/EBOOT.BIN && GEN_OPT=1 bash scripts/build_native.sh pes6 disc0:/PSP_GAME/SYSDIR/EBOOT.BIN'
done
echo "Bounded automatic recovery ended after $N iterations; run a smoke test for the latest generated executable."
