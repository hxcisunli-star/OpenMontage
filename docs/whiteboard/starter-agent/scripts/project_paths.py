"""Paths shared by agent lesson tools; supports a custom projects directory."""
import os
from pathlib import Path

P = Path(__file__).resolve().parents[1]
PID = "__PID__"
LESSON = int("__N__")

def find_root():
    if os.environ.get("OPENMONTAGE_ROOT"):
        return Path(os.environ["OPENMONTAGE_ROOT"]).resolve()
    for base in (P, Path.cwd(), *P.parents, *Path.cwd().parents):
        if (base / "docs/whiteboard/series.yaml").is_file():
            return base
    raise RuntimeError("找不到仓库 docs/whiteboard/series.yaml；请设置 OPENMONTAGE_ROOT")

ROOT = find_root()
