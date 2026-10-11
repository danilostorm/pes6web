#!/usr/bin/env bash
# PSP Web Recomp's interface: decrypt-adapter.sh <encrypted.bin> <out.elf>
set -euo pipefail
[[ $# -eq 2 ]] || { echo 'Usage: decrypt-adapter.sh INPUT OUTPUT' >&2; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${PSPDECRYPT_BIN:-$ROOT/work/pspdecrypt/pspdecrypt}"
[[ -x "$BIN" ]] || { echo "Cannot find pspdecrypt: $BIN; run scripts/build-decrypter.sh" >&2; exit 1; }
"$BIN" -o "$2" "$1"
python3 - "$2" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]); valid=p.is_file() and p.stat().st_size>52 and p.open('rb').read(4)==b'\x7fELF'
if not valid:
    sys.exit('Decrypt error: expected a plain ELF output, no recompilation attempted')
print('Decrypted ELF validated:',p.stat().st_size,'bytes')
PY
