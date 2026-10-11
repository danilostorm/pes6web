#!/usr/bin/env bash
# Prepare the open-source toolchain (no game files are downloaded).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/work/psp-web-recomp"
REF="${PES6_UPSTREAM_REF:-95d088239cfb09c22fe4ee9d98671ede371f2a4b}"
if [[ ! -d "$DEST/.git" ]]; then
  mkdir -p "$(dirname "$DEST")"
  git clone https://github.com/snuri00/psp-web-recomp.git "$DEST"
fi
CURRENT="$(git -C "$DEST" rev-parse HEAD)"
if [[ "$CURRENT" != "$REF" ]]; then
  git -C "$DEST" fetch origin "$REF"
  git -C "$DEST" checkout --detach "$REF"
fi
(cd "$DEST" && bash scripts/setup.sh)
echo "Toolchain ready: $DEST @ $(git -C "$DEST" rev-parse --short HEAD)"
