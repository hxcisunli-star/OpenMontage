"""Single frames (seconds list) -> renders/stills/tNNNNN.png, one bundle for all.  Old per-frame version: render_stills_legacy.py.
Whole-board key-moment sheets:  .venv/bin/python docs/whiteboard_render.py projects/__PID__ --contact [K4 ...]"""
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.exit(subprocess.call([str(ROOT / ".venv/bin/python"), str(ROOT / "docs/whiteboard_render.py"), "projects/__PID__", "--stills", *sys.argv[1:]], cwd=ROOT))
