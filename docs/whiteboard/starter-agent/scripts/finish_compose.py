"""Repository tool wrapper for this lesson."""
import subprocess
import sys
from project_paths import ROOT, P
raise SystemExit(subprocess.call([sys.executable, str(ROOT / "docs/whiteboard_finish_compose.py"), str(P), *sys.argv[1:]], cwd=ROOT))
