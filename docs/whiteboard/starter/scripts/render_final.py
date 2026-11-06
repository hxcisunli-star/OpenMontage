"""Chunked, cached full render (only boards whose fingerprint changed are re-rendered); lint runs first.
Old single-pass render is kept as render_final_full.py (fallback).  Extra args are passed on, e.g.  --force K4  or  --plan."""
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.exit(subprocess.call([str(ROOT / ".venv/bin/python"), str(ROOT / "docs/whiteboard_render.py"), "projects/__PID__", "--final", *sys.argv[1:]], cwd=ROOT))
