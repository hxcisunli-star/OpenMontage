"""Edit stage, last step: re-runs the checks, reads the measured files, writes the edit checkpoint (awaiting_human).  Nothing in the metadata is typed by hand.
Run (repo root, after rebuild_edit.sh, `docs/whiteboard_sfx.py apply`, the layout check with --json -> validation/layout-check.json, and the sample clips):
  PYTHONPATH=. .venv/bin/python projects/__PID__/scripts/finish_edit.py"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from project_paths import ROOT, P
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "docs"))
os.chdir(ROOT)
from lib.checkpoint import write_checkpoint  # noqa: E402
from schemas.artifacts import validate_artifact  # noqa: E402
from whiteboard_boardtime import board_rows  # noqa: E402

PID = "__PID__"
A = P / "artifacts"
ed = json.loads((A / "edit_decisions.json").read_text(encoding="utf-8"))
try:
    validate_artifact("edit_decisions", ed)
    schema = "valid"
except Exception as e:   # say so instead of hiding it
    schema = "NOT valid: " + str(e)[:300]
lint = subprocess.run([sys.executable, str(ROOT / "docs/whiteboard_lint.py"), str(P)], capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(ROOT)))
m = re.search(r"lint: (\d+) error\(s\), (\d+) warning\(s\)", lint.stdout + lint.stderr)
rows = board_rows(P)
margin = min(r["margin"] for r in rows)
lay = json.loads((P / "validation/layout-check.json").read_text(encoding="utf-8"))
# E107: the sound profile is read from what was applied, never typed: scripts/sfx_profile.txt (written before `whiteboard_sfx.py apply`) and the real cue list of that profile
_profile = (P / "scripts/sfx_profile.txt").read_text(encoding="utf-8").strip()
_cues = json.loads((P / "validation/sfx-cues.json").read_text(encoding="utf-8"))
_by = {}
for _c in _cues["cues"]:
    _by[_c["name"]] = _by.get(_c["name"], 0) + 1
props = json.loads((P / "render_props.json").read_text(encoding="utf-8"))
narr_src = props["audio"]["narration"]["src"]
SFX_TEXT = "profile '%s': %d cues %s, narration -> %s" % (_profile, len(_cues["cues"]), json.dumps(_by, ensure_ascii=False), narr_src.split("/")[-1])
assert narr_src.endswith("narration_sfx.wav"), "run docs/whiteboard_sfx.py apply after the last build: render_props points to " + narr_src
samples = sorted((P / "renders").glob("sample_*.mp4"))
assert samples, "no sample clips in renders/"
sample_rows = []
for s in samples:
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(s)]).decode())
    sample_rows.append(f"renders/{s.name} ({dur:.2f} s)")
contact = sorted(p.name for p in (P / "renders/contact").glob("K*.png"))
n_still = len(list((P / "renders/contact/stills").glob("*.png")))
devs = json.loads((P / "scripts/edit_deviations.json").read_text(encoding="utf-8"))
total = max(c["out_seconds"] for c in ed["cuts"])
meta = {"cuts": len(ed["cuts"]), "whiteboard_cuts": sum(1 for c in ed["cuts"] if c["source"].startswith("whiteboard:")), "total_video_seconds": round(total, 2), "edit_decisions_schema": schema,
        "lint": ("%s errors %s warnings" % (m.group(1), m.group(2))) if m else "lint output not parsed",
        "last_item_check": "min margin %.2f s over %d whiteboard cuts (needs >= 0.6)" % (margin, len(rows)),
        "layout_check": "%d findings in %d sample frames of %d whiteboard cuts; findings require this lesson's documented review; see edit_deviations" % (len(lay["findings"]), len(lay["frames"]), sum(1 for c in ed["cuts"] if c["source"].startswith("whiteboard:"))),
        "layout_findings": [{"rule": f["rule"], "cut": f["cut"], "t0": f["t0"], "t1": f["t1"], "msg": f["msg"]} for f in lay["findings"]],
        "sfx": SFX_TEXT,
        "sample": sample_rows, "contact_sheets": contact, "contact_key_frames": n_still, "deviations_listed": len(devs)}
assert m and m.group(1) == "0" and margin >= 0.6, meta
(P / "validation").mkdir(exist_ok=True)
(P / "validation/edit-report.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(meta, ensure_ascii=False, indent=1))
print(write_checkpoint(P.parent, PID, "edit", "awaiting_human", {"edit_decisions": ed}, pipeline_type="animated-explainer", human_approval_required=True, metadata=meta))
