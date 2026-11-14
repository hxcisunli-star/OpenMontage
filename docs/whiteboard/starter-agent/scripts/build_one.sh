#!/bin/bash
# usage: bash scripts/build_one.sh s3 [--assemble-only]
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
if [ "$#" -eq 0 ]; then
  echo '用法：build_one.sh s正整数 [--assemble-only]' >&2
  exit 2
fi
SECTION=$1
shift
exec "${PYTHON:-python3}" "$SCRIPT_DIR/build_parts.py" --section "$SECTION" "$@"
