#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

if [ -x ".venv/bin/pytest" ]; then
    QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v tests/
fi

bash packaging/build_macos.sh
