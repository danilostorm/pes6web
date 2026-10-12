#!/usr/bin/env bash
# Local-only diagnostic for the currently observed 0x0897FD08 halt.
# No SSH and no network; does not rebuild or modify binaries.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${PES6_WORK_DIR:-/mnt/user/Downloads/pes6web-work}"
python3 "$ROOT/tools/diagnose_pc.py" \
  --elf "$WORK/psp-web-recomp/games/pes6/root/EBOOT.BIN" \
  --generated "$WORK/psp-web-recomp/PSPRecomp/profiles/web/generated/pes6" \
  --address 0x0897FD08 \
  --address 0x0897E524 \
  --address 0x089943DC
