"""Check that the last handwriting item of every whiteboard cut finishes before the board fades out (lesson 40 lesson).
Run after rebuild_edit.sh:  .venv/bin/python docs/whiteboard_last_item_check.py projects/<lesson>
Prints, per cut, when the last item ends, when the 0.4 s fade-out starts and the margin; margin < 0.6 s is reported as TOO LATE."""
import json, sys
from pathlib import Path
P = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
sc = json.load(open(P / "artifacts/whiteboard_scenes.json", encoding="utf-8"))
ed = json.load(open(P / "artifacts/edit_decisions.json", encoding="utf-8"))
cuts = {c["id"]: c for c in ed["cuts"]}
bad = 0
for k, v in sc.items():
    c = cuts[k]; length = c["out_seconds"] - c["in_seconds"]
    ends = sorted((round(it["at"] + it.get("dur", 0.5), 2), it["kind"], str(it.get("text", it.get("shape", "")))[:24]) for it in v["items"] if it["kind"] in ("write", "stroke", "code", "image"))
    last = ends[-1]; fade = length - 0.4; margin = fade - last[0]
    bad += margin < 0.6
    print(k, "len", round(length, 1), "last item ends", last[0], "fade starts", round(fade, 1), "margin", round(margin, 2), last[1:], "OK" if margin >= 0.6 else "TOO LATE")
sys.exit(1 if bad else 0)
