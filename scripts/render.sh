#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPS_VENV="${ROOT}/.deps/venv"

if [ -f "${DEPS_VENV}/bin/python3" ]; then
  PYTHON="${DEPS_VENV}/bin/python3"
else
  PYTHON="python3"
fi

"${PYTHON}" "${ROOT}/src/thechessstuff_reel.py"
