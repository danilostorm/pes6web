#!/usr/bin/env bash
# Builds using an isolated Ubuntu toolchain, storing ALL large work outside Unraid docker.img.
# Usage: PES6_WORK_DIR=/mnt/user/Downloads/pes6web-work bash scripts/unraid-build.sh /mnt/user/Downloads/pes6.iso
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $# -ge 1 ]] || { echo 'Usage: scripts/unraid-build.sh /path/to/PES6.iso [--native] [--opt N]' >&2; exit 2; }
SOURCE="$1"; shift
[[ -e "$SOURCE" ]] || { echo "Game source not found: $SOURCE" >&2; exit 1; }
command -v docker >/dev/null || { echo 'Docker is not installed' >&2; exit 1; }
SOURCE="$(realpath "$SOURCE")"
# Do not use the small Unraid Docker overlay for extracted ISO or generated C++.
WORK="${PES6_WORK_DIR:-/mnt/user/Downloads/pes6web-work}"
mkdir -p "$WORK" "$ROOT/dist"
WORK="$(realpath "$WORK")"
if [[ "$WORK" == "$ROOT" || "$ROOT" == "$WORK"/* ]]; then
  echo 'PES6_WORK_DIR must be outside the repository directory' >&2; exit 1
fi
if [[ "$WORK" == "$ROOT"/* ]]; then
  echo 'Use an external path (e.g. /mnt/user/Downloads/pes6web-work) for PES6_WORK_DIR' >&2; exit 1
fi
if [[ -d "$SOURCE" ]]; then
  TARGET='/input/extracted'
else
  TARGET='/input/PES6.iso'
fi
IMAGE="${PES6_BUILDER_IMAGE:-pes6web-builder:local}"
echo "Builder: $IMAGE"
echo "Input: $SOURCE (read-only)"
echo "Scratch on Unraid: $WORK"
LOGDIR="$WORK/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/unraid-build-$(date +%Y%m%d-%H%M%S).log"
echo "Full build log: $LOG"
# Capture bootstrap, decryption and recompilation failures, not only the final port stage.
docker build -q -f "$ROOT/deploy/Dockerfile.builder" -t "$IMAGE" "$ROOT" 2>&1 | tee -a "$LOG"
docker run --rm -i \
  --shm-size=2g \
  -v "$ROOT:/project" \
  -v "$WORK:/project/work" \
  -v "$SOURCE:$TARGET:ro" \
  -w /project \
  -e "PES6_UPSTREAM_REF=${PES6_UPSTREAM_REF:-95d088239cfb09c22fe4ee9d98671ede371f2a4b}" \
  -e "JOBS=${JOBS:-4}" \
  "$IMAGE" bash -lc \
  'bash scripts/bootstrap.sh && bash scripts/build-decrypter.sh && bash scripts/port.sh "$@"' _ "$TARGET" "$@" 2>&1 | tee -a "$LOG"
echo "Build directory: $ROOT/dist"
echo "To serve: PES6_WORK_DIR='$WORK' docker compose up -d"
