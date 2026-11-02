#!/bin/bash
# Lesson-specific offline checks belong in code/validate.py. No model or rendering calls here.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
if [ ! -f "$PROJECT_DIR/code/validate.py" ]; then
  echo '请作者先创建 code/validate.py：用离线假模型验证本课示例及预期结果。' >&2
  exit 2
fi
mkdir -p "$PROJECT_DIR/validation"
"${PYTHON:-python3}" "$PROJECT_DIR/code/validate.py" 2>&1 | tee "$PROJECT_DIR/validation/all-outputs.txt"
