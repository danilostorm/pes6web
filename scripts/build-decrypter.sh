#!/usr/bin/env bash
# GPLv3 utility stays external and is never copied into this repo.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/work/pspdecrypt"
command -v git >/dev/null || { echo 'Install git first' >&2; exit 1; }
command -v make >/dev/null || { echo 'Install make first' >&2; exit 1; }
command -v clang++ >/dev/null || { echo 'Install clang++ first' >&2; exit 1; }
[[ -d "$DEST/.git" ]] || git clone https://github.com/John-K/pspdecrypt.git "$DEST"
make -C "$DEST" -j "${JOBS:-2}"
[[ -x "$DEST/pspdecrypt" ]] || { echo 'pspdecrypt compilation failed' >&2; exit 1; }
echo "Decrypter ready: $DEST/pspdecrypt"
