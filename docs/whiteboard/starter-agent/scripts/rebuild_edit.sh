#!/bin/bash
# Assemble all _board_sN.py in numeric order, then execute the lint and last-item check.
# PYTHON defaults to the repo's .venv python (it has PIL; plain python3 here does not): lesson 3 lost a run to that.  pose_metrics.json (display size of every pose) is made once if it is missing.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(cd -- "$SCRIPT_DIR/../../.." && pwd)
if [ -z "${PYTHON:-}" ]; then
  if [ -x "$ROOT_DIR/.venv/bin/python" ]; then PYTHON="$ROOT_DIR/.venv/bin/python"; else PYTHON=python3; fi
fi
export OPENMONTAGE_ROOT="${OPENMONTAGE_ROOT:-$ROOT_DIR}" PYTHONPATH="${PYTHONPATH:-$ROOT_DIR}"
[ -f "$SCRIPT_DIR/../assets/images/pose_metrics.json" ] || "$PYTHON" "$SCRIPT_DIR/pose_metrics.py"
"$PYTHON" "$SCRIPT_DIR/build_parts.py" "$@"
# lessons whose partner speaks: the partner must stand on stage for every one of its real clips and its bubbles must read word for word
if grep -q '"partner_lines"' "$SCRIPT_DIR/../artifacts/script.json" 2>/dev/null; then "$PYTHON" "$ROOT_DIR/docs/whiteboard_partner_check.py" "$SCRIPT_DIR/.."; fi
