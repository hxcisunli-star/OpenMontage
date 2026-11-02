#!/bin/bash
# Assemble all _board_sN.py in numeric order, then execute the lint and last-item check.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
exec "${PYTHON:-python3}" "$SCRIPT_DIR/build_parts.py" "$@"
