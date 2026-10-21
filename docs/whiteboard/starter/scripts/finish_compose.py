"""Compose-stage report for lesson __N__ FROM MEASUREMENTS: run docs/whiteboard_verify.py first (it writes validation/compose-measured.json), look at the contact
sheets, write validation/compose-notes.json (see docs/whiteboard_finish_compose.py), then run this. Nothing in here is typed by hand."""
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.exit(subprocess.call([str(ROOT / ".venv/bin/python"), str(ROOT / "docs/whiteboard_finish_compose.py"), str(ROOT / "projects/__PID__")], cwd=ROOT))
