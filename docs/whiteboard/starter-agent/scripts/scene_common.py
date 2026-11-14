"""Shared helpers for the scene-plan stage (used by validate_section.py and by build_scene_plan.py): plain-text anchoring and the time estimate.
The estimate is only a placeholder until the real TTS timeline exists; the edit stage re-anchors every event on the measured subtitle timing."""
import json
import re
from pathlib import Path

from project_paths import ROOT
import sys
sys.path.insert(0, str(ROOT / "docs"))
from whiteboard_lessons import series_config
_CFG = series_config("agent")
ALLOWED_POSES = {n for n in _CFG["cast_assets"] if n.startswith(("teacher_", "robot_", "card_"))}
DEVICES = _CFG["devices"]

STRIP = "，。？！：；、,.?!:;…“”‘’（）()"


def plain(t):
    return "".join(c for c in t if c not in STRIP and not c.isspace())


def load_script(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Timing:
    """est(i): estimated second at which the i-th plain character of section `sid` starts being spoken (quiz silences included)."""

    def __init__(self, script, sid):
        self.sec = next(s for s in script["sections"] if s["id"] == sid)
        self.pt = plain(self.sec["text"])
        self.n = len(self.pt)
        self.qs = [q for q in script["metadata"]["quiz_pauses"] if q["section_id"] == sid]
        self.q_ends = [self.pt.find(plain(q["after_exact_text"])) + len(plain(q["after_exact_text"])) for q in self.qs]
        assert all(e >= len(plain(q["after_exact_text"])) for e, q in zip(self.q_ends, self.qs)), sid
        self.start, self.end = self.sec["start_seconds"], self.sec["end_seconds"]
        self.speech = (self.end - self.start) - 3.0 * len(self.qs)

    def est(self, i):
        return self.start + i / self.n * self.speech + 3.0 * sum(1 for q in self.q_ends if i >= q)
