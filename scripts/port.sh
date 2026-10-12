#!/usr/bin/env bash
# Builds PES 6 PSP web port using upstream PSP Web Recomp.
# Usage: scripts/port.sh /local/path/PES6.iso [--native] [--opt N]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="$ROOT/work/psp-web-recomp"
NAME=pes6
[[ $# -ge 1 ]] || { echo 'Usage: scripts/port.sh ISO_OR_EXTRACTED_FOLDER [--native] [--opt N]' >&2; exit 2; }
SOURCE="$1"; shift
[[ -e "$SOURCE" ]] || { echo "Game source not found: $SOURCE" >&2; exit 1; }
SOURCE="$(realpath "$SOURCE")"
[[ -f "$UPSTREAM/scripts/port.sh" ]] || { echo 'Run scripts/bootstrap.sh first' >&2; exit 1; }
if [[ -d "$SOURCE" ]]; then
  python3 "$ROOT/tools/inspect_psp.py" "$SOURCE"
fi
if [[ -n "${PES6_DECRYPTED_ELF:-}" ]]; then
  [[ -r "$PES6_DECRYPTED_ELF" ]] || { echo 'PES6_DECRYPTED_ELF is unreadable' >&2; exit 1; }
  PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 - "$PES6_DECRYPTED_ELF" <<'PY'
import sys
from pathlib import Path
from tools.inspect_psp import elf_info
p=Path(sys.argv[1]); info=elf_info(p.read_bytes())
assert info['is_psp_compatible'], 'Expected a MIPS PSP ELF'
print('Using decrypted ELF:', info['entry_point'])
PY
  mkdir -p "$UPSTREAM/games/$NAME/root"
  cp "$PES6_DECRYPTED_ELF" "$UPSTREAM/games/$NAME/root/EBOOT.BIN"
fi
if [[ -z "${PSP_DECRYPT:-}" && -x "$ROOT/work/pspdecrypt/pspdecrypt" ]]; then
  export PSP_DECRYPT="$ROOT/scripts/decrypt-adapter.sh"
fi
# PES6 code section at 0x0897FD08 is reached indirectly and missing from base CFG.
# Keep overrides scoped to the PES6 build, never modify the retail ISO.
if [[ -n "${PES6_EXTRA_SEEDS:-}" ]]; then
  export PSPRECOMP_EXTRA_SEEDS="$PES6_EXTRA_SEEDS"
elif [[ -s "$ROOT/work/diagnostics/verified-extra-seeds.txt" ]]; then
  export PSPRECOMP_EXTRA_SEEDS="$(tr -d '\r\n' < "$ROOT/work/diagnostics/verified-extra-seeds.txt")"
else
  export PSPRECOMP_EXTRA_SEEDS=0x0897FD08
fi
echo "Opt-in CFG recovery entries: $(awk -F, '{print NF}' <<< "$PSPRECOMP_EXTRA_SEEDS")"
# Bounded J/JR fallthrough discovery based on observed native guest halts.
export PSPRECOMP_FALLTHROUGH_RANGES="${PES6_FALLTHROUGH_RANGES:-0x08984000-0x08987000,0x088B0000-0x088C0000,0x088C0000-0x088C5000}"
echo "Scoped post-J/JR discovery: $PSPRECOMP_FALLTHROUGH_RANGES"
mkdir -p "$ROOT/work/logs"
LOG="$ROOT/work/logs/port-$(date +%Y%m%d-%H%M%S).log"
echo "Porting $NAME; local log: $LOG"
(cd "$UPSTREAM" && bash scripts/port.sh "$NAME" "$SOURCE" "$@") 2>&1 | tee "$LOG"
WEB_DIR="$UPSTREAM/build/web-$NAME/profiles/web"
[[ -f "$WEB_DIR/index.html" ]] || { echo "Build finished without index.html at $WEB_DIR" >&2; exit 1; }
mkdir -p "$ROOT/dist"
cp -a "$WEB_DIR/." "$ROOT/dist/"
echo "Web build is now in $ROOT/dist (NOT a proof the game is playable)"
echo 'Test via scripts/serve.sh; keep game data and generated code PRIVATE.'
