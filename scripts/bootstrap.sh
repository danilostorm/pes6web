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
# This idempotent patch only changes open-source host HLE; never game code.
python3 "$ROOT/tools/patch_psp_modulemgr.py" "$DEST"
python3 "$ROOT/tools/patch_psp_extra_seeds.py" "$DEST"
python3 "$ROOT/tools/patch_psp_fallthrough.py" "$DEST"
python3 "$ROOT/tools/patch_psp_umdhle.py" "$DEST"
python3 "$ROOT/tools/patch_psp_umd_callback_dispatch.py" "$DEST"
python3 "$ROOT/tools/patch_psp_native_diagnostics.py" "$DEST"
python3 "$ROOT/tools/patch_psp_private_diagnostics.py" "$DEST"
python3 "$ROOT/tools/patch_psp_raw_sector_io.py" "$DEST"
python3 "$ROOT/tools/patch_psp_ge_event_trace.py" "$DEST"
python3 "$ROOT/tools/patch_psp_ge_callback_trace.py" "$DEST"
python3 "$ROOT/tools/patch_psp_ge_finish_queue.py" "$DEST"
python3 "$ROOT/tools/patch_psp_display_hcount.py" "$DEST"
python3 "$ROOT/tools/patch_psp_sema_status.py" "$DEST"
python3 "$ROOT/tools/patch_psp_devctl.py" "$DEST"
python3 "$ROOT/tools/patch_psp_alarm.py" "$DEST"
# Rebuild analyzer/codegen tools only when upstream sources changed (Ninja is incremental).
(cd "$DEST" && bash scripts/build_tools.sh)
echo "Toolchain ready: $DEST @ $(git -C "$DEST" rev-parse --short HEAD)"
