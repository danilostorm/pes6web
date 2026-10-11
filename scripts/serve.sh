#!/usr/bin/env bash
# Test server from upstream; handles /disc, Range requests and isolation headers.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UPSTREAM="$ROOT/work/psp-web-recomp"
[[ -f "$UPSTREAM/build/web-pes6/profiles/web/index.html" ]] || { echo 'No compiled web build: run scripts/port.sh first' >&2; exit 1; }
cd "$UPSTREAM"
exec bash scripts/serve.sh pes6 "${1:-8613}"
